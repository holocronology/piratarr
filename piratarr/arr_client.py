"""Sonarr and Radarr API client.

Provides unified access to Sonarr (TV) and Radarr (Movies) APIs for
discovering media and locating subtitle files on disk.
"""

import logging
import os
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class MediaItem:
    """Represents a movie or TV episode from Sonarr/Radarr."""

    title: str
    year: int | None
    path: str
    media_type: str  # "movie" or "episode"
    arr_id: int
    # For episodes
    series_title: str | None = None
    season_number: int | None = None
    episode_number: int | None = None

    @property
    def display_title(self) -> str:
        if self.media_type == "episode" and self.series_title:
            return f"{self.series_title} S{self.season_number:02d}E{self.episode_number:02d} - {self.title}"
        if self.year:
            return f"{self.title} ({self.year})"
        return self.title


class ArrClient:
    """Base client for *arr API communication."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({"X-Api-Key": self.api_key})

    def _get(self, endpoint: str, params: dict | None = None) -> dict | list:
        url = f"{self.base_url}/api/v3/{endpoint}"
        try:
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error("API request failed: %s %s - %s", "GET", url, e)
            raise

    def test_connection(self) -> bool:
        """Test if the API connection is working."""
        try:
            self._get("system/status")
            return True
        except Exception:
            return False


class RadarrClient(ArrClient):
    """Client for Radarr (movie management) API."""

    def get_movies(self) -> list[MediaItem]:
        """Fetch all movies from Radarr."""
        data = self._get("movie")
        items = []
        for movie in data:
            if not movie.get("hasFile"):
                continue
            movie_file = movie.get("movieFile", {})
            file_path = movie_file.get("path", "")
            if not file_path:
                continue
            items.append(
                MediaItem(
                    title=movie["title"],
                    year=movie.get("year"),
                    path=file_path,
                    media_type="movie",
                    arr_id=movie["id"],
                )
            )
        return items


class SonarrClient(ArrClient):
    """Client for Sonarr (TV series management) API."""

    def get_series(self) -> list[dict]:
        """Fetch all TV series from Sonarr."""
        return self._get("series")

    def get_episodes(self, series_id: int) -> list[dict]:
        """Fetch all episodes for a given series."""
        return self._get("episode", params={"seriesId": series_id})

    def get_episode_files(self, series_id: int) -> list[dict]:
        """Fetch all episode files for a given series."""
        return self._get("episodefile", params={"seriesId": series_id})

    def get_all_episodes(self) -> list[MediaItem]:
        """Fetch all episodes with files across all series."""
        series_list = self.get_series()
        items = []
        for series in series_list:
            series_id = series["id"]
            series_title = series["title"]

            try:
                episode_files = self.get_episode_files(series_id)
            except Exception:
                logger.warning("Failed to get episode files for series %s", series_title)
                continue

            # Build a map of episode file IDs to paths
            file_map = {ef["id"]: ef.get("path", "") for ef in episode_files}

            try:
                episodes = self.get_episodes(series_id)
            except Exception:
                logger.warning("Failed to get episodes for series %s", series_title)
                continue

            for ep in episodes:
                if not ep.get("hasFile"):
                    continue
                ep_file_id = ep.get("episodeFileId")
                file_path = file_map.get(ep_file_id, "")
                if not file_path:
                    continue
                items.append(
                    MediaItem(
                        title=ep.get("title", "Unknown"),
                        year=None,
                        path=file_path,
                        media_type="episode",
                        arr_id=ep["id"],
                        series_title=series_title,
                        season_number=ep.get("seasonNumber", 0),
                        episode_number=ep.get("episodeNumber", 0),
                    )
                )
        return items


def apply_path_mapping(path: str, mappings: list[dict]) -> str:
    """Remap a path from an *arr container to the local filesystem.

    Sonarr/Radarr report paths as they appear inside their own containers.
    This function translates those paths using configured mappings so that
    Piratarr can access the files on its own filesystem.

    Args:
        path: Original path from the *arr API.
        mappings: List of {"remote_path": ..., "local_path": ...} dicts.

    Returns:
        Remapped path, or the original if no mapping matches.
    """
    for mapping in mappings:
        remote = mapping.get("remote_path", "")
        local = mapping.get("local_path", "")
        if not remote or not local:
            continue
        # Normalise so that "/movies" and "/movies/" both work
        remote_norm = remote.rstrip("/")
        if path == remote_norm or path.startswith(remote_norm + "/"):
            return local.rstrip("/") + path[len(remote_norm):]
    return path


def find_subtitle_files(media_path: str) -> list[str]:
    """Find SRT subtitle files adjacent to a media file.

    Looks in the same directory as the media file for .srt files
    that share the same base name or are in a 'Subs' subdirectory.

    Args:
        media_path: Path to the media file (movie/episode).

    Returns:
        List of paths to found SRT files.
    """
    srt_files = []
    media_dir = os.path.dirname(media_path)
    media_base = os.path.splitext(os.path.basename(media_path))[0]

    if not os.path.isdir(media_dir):
        return srt_files

    # Check files in the same directory
    for filename in os.listdir(media_dir):
        if not filename.lower().endswith(".srt"):
            continue
        # Skip already-translated pirate subtitles
        if ".pirate." in filename.lower():
            continue
        filepath = os.path.join(media_dir, filename)
        # Match files that start with the media base name
        if filename.startswith(media_base):
            srt_files.append(filepath)

    # Also check a "Subs" subdirectory (common for some setups)
    subs_dir = os.path.join(media_dir, "Subs")
    if os.path.isdir(subs_dir):
        for filename in os.listdir(subs_dir):
            if not filename.lower().endswith(".srt"):
                continue
            if ".pirate." in filename.lower():
                continue
            srt_files.append(os.path.join(subs_dir, filename))

    return srt_files
