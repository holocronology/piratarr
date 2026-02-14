"""Background media scanner and subtitle processor.

Periodically scans Sonarr/Radarr libraries for media with subtitles
and queues them for pirate-speak translation.
"""

import logging
import os
import threading
import time
from datetime import datetime, timezone

from piratarr.arr_client import RadarrClient, SonarrClient, find_subtitle_files
from piratarr.database import MediaCache, TranslationJob, get_config, get_session
from piratarr.subtitle import get_pirate_srt_path, process_srt_file

logger = logging.getLogger(__name__)


class Scanner:
    """Background scanner that discovers media and translates subtitles."""

    def __init__(self):
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._is_scanning = False
        self._last_scan: datetime | None = None
        self._scan_interval = 3600  # Default: scan every hour

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def is_scanning(self) -> bool:
        return self._is_scanning

    @property
    def last_scan(self) -> datetime | None:
        return self._last_scan

    def start(self) -> None:
        """Start the background scanner thread."""
        if self.is_running:
            logger.warning("Scanner is already running")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Scanner started")

    def stop(self) -> None:
        """Stop the background scanner thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10)
        logger.info("Scanner stopped")

    def scan_now(self) -> dict:
        """Trigger an immediate scan (can be called from API).

        Returns a summary of the scan results.
        """
        return self._do_scan()

    def _run_loop(self) -> None:
        """Main scanner loop."""
        # Do an initial scan shortly after startup
        time.sleep(5)
        while not self._stop_event.is_set():
            try:
                interval = int(get_config("scan_interval", str(self._scan_interval)))
            except (TypeError, ValueError):
                interval = self._scan_interval

            self._do_scan()
            self._stop_event.wait(timeout=interval)

    def _do_scan(self) -> dict:
        """Perform a full scan cycle."""
        self._is_scanning = True
        summary = {"movies_found": 0, "episodes_found": 0, "subtitles_found": 0, "translations_queued": 0}

        try:
            # Scan Radarr (movies)
            radarr_url = get_config("radarr_url")
            radarr_key = get_config("radarr_api_key")
            if radarr_url and radarr_key:
                try:
                    radarr = RadarrClient(radarr_url, radarr_key)
                    movies = radarr.get_movies()
                    summary["movies_found"] = len(movies)
                    self._process_media_items(movies, summary)
                except Exception as e:
                    logger.error("Radarr scan failed: %s", e)

            # Scan Sonarr (TV)
            sonarr_url = get_config("sonarr_url")
            sonarr_key = get_config("sonarr_api_key")
            if sonarr_url and sonarr_key:
                try:
                    sonarr = SonarrClient(sonarr_url, sonarr_key)
                    episodes = sonarr.get_all_episodes()
                    summary["episodes_found"] = len(episodes)
                    self._process_media_items(episodes, summary)
                except Exception as e:
                    logger.error("Sonarr scan failed: %s", e)

            self._last_scan = datetime.now(timezone.utc)
            logger.info(
                "Scan complete: %d movies, %d episodes, %d subtitles, %d queued",
                summary["movies_found"],
                summary["episodes_found"],
                summary["subtitles_found"],
                summary["translations_queued"],
            )
        except Exception as e:
            logger.error("Scan failed: %s", e)
        finally:
            self._is_scanning = False

        return summary

    def _process_media_items(self, items, summary: dict) -> None:
        """Process a list of media items — find subtitles and queue translations."""
        session = get_session()
        try:
            for item in items:
                srt_files = find_subtitle_files(item.path)

                # Update media cache
                cached = session.query(MediaCache).filter_by(arr_id=item.arr_id, media_type=item.media_type).first()
                if not cached:
                    cached = MediaCache(
                        arr_id=item.arr_id,
                        title=item.display_title,
                        media_type=item.media_type,
                        path=item.path,
                    )
                    session.add(cached)

                cached.has_subtitle = len(srt_files) > 0
                cached.last_scanned = datetime.now(timezone.utc)

                for srt_path in srt_files:
                    summary["subtitles_found"] += 1
                    pirate_path = get_pirate_srt_path(srt_path)

                    # Skip if pirate subtitle already exists
                    if os.path.exists(pirate_path):
                        cached.has_pirate_subtitle = True
                        continue

                    # Skip if there's already a pending/processing job for this file
                    existing_job = (
                        session.query(TranslationJob)
                        .filter_by(source_path=srt_path)
                        .filter(TranslationJob.status.in_(["pending", "processing"]))
                        .first()
                    )
                    if existing_job:
                        continue

                    # Queue a new translation job
                    auto_translate = get_config("auto_translate", "true")
                    if auto_translate.lower() == "true":
                        job = TranslationJob(
                            media_title=item.display_title,
                            media_type=item.media_type,
                            source_path=srt_path,
                            status="pending",
                        )
                        session.add(job)
                        summary["translations_queued"] += 1

            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("Error processing media items: %s", e)
        finally:
            session.close()

        # Process pending translation jobs
        self._process_pending_jobs()

    def _process_pending_jobs(self) -> None:
        """Process all pending translation jobs."""
        session = get_session()
        try:
            pending_jobs = session.query(TranslationJob).filter_by(status="pending").all()
            for job in pending_jobs:
                job.status = "processing"
                session.commit()

                try:
                    output_path = process_srt_file(job.source_path)
                    job.output_path = output_path
                    job.status = "completed"
                    job.completed_at = datetime.now(timezone.utc)

                    # Count subtitle entries
                    from piratarr.subtitle import parse_srt

                    with open(job.source_path, "r", encoding="utf-8-sig") as f:
                        subtitle_file = parse_srt(f.read())
                    job.subtitle_count = subtitle_file.count

                    logger.info("Translated: %s -> %s", job.source_path, output_path)
                except Exception as e:
                    job.status = "failed"
                    job.error_message = str(e)
                    logger.error("Translation failed for %s: %s", job.source_path, e)

                session.commit()
        except Exception as e:
            session.rollback()
            logger.error("Error processing jobs: %s", e)
        finally:
            session.close()


# Singleton scanner instance
scanner = Scanner()
