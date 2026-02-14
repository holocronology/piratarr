# Piratarr

Automatically generate pirate speak subtitles for your media library. A Bazarr-inspired Docker application that integrates with Sonarr and Radarr.

## Features

- Connects to **Sonarr** (TV) and **Radarr** (Movies) to discover your media library
- Scans for existing `.srt` subtitle files alongside your media
- Translates subtitles into pirate speak and saves as `*.pirate.srt`
- Web dashboard to manage, trigger, and monitor translations
- Background scanner with configurable scan intervals
- Translation preview tool built into the web UI
- Configurable via environment variables or the web interface
- Dockerized with docker-compose support

## Quick Start

### Docker Compose (Recommended)

1. Clone the repository:
   ```bash
   git clone https://github.com/holocronology/piratarr.git
   cd piratarr
   ```

2. Edit `docker-compose.yml` to mount your media directories and optionally set Sonarr/Radarr credentials:
   ```yaml
   volumes:
     - ./config:/config
     - /path/to/movies:/movies
     - /path/to/tv:/tv
   environment:
     - RADARR_URL=http://radarr:7878
     - RADARR_API_KEY=your_api_key
     - SONARR_URL=http://sonarr:8989
     - SONARR_API_KEY=your_api_key
   ```

3. Start the container:
   ```bash
   docker compose up -d
   ```

4. Open the web UI at `http://localhost:6969`

### Docker CLI

```bash
docker build -t piratarr .
docker run -d \
  --name piratarr \
  -p 6969:6969 \
  -v ./config:/config \
  -v /path/to/movies:/movies \
  -v /path/to/tv:/tv \
  -e RADARR_URL=http://radarr:7878 \
  -e RADARR_API_KEY=your_api_key \
  piratarr
```

## Configuration

Settings can be configured via environment variables or through the web UI under **Settings**.

| Environment Variable | Description | Default |
|---|---|---|
| `RADARR_URL` | Radarr base URL | _(none)_ |
| `RADARR_API_KEY` | Radarr API key | _(none)_ |
| `SONARR_URL` | Sonarr base URL | _(none)_ |
| `SONARR_API_KEY` | Sonarr API key | _(none)_ |
| `SCAN_INTERVAL` | Seconds between library scans | `3600` |
| `AUTO_TRANSLATE` | Auto-translate discovered subtitles | `true` |
| `PIRATARR_PORT` | Web UI port | `6969` |
| `PIRATARR_CONFIG_DIR` | Config/database directory | `/config` |

## How It Works

1. Piratarr connects to your Sonarr/Radarr instances to discover media files
2. It scans the filesystem for `.srt` subtitle files next to each media file
3. Each subtitle is parsed, translated to pirate speak, and written as a `.pirate.srt` file
4. The translation uses a dictionary-based engine with word/phrase substitutions, `-ing` to `-in'` contractions, and random pirate exclamations

### Translation Examples

| Original | Pirate Speak |
|---|---|
| "Hello my friend" | "Ahoy me hearty" |
| "I am looking for the treasure" | "I be lookin' fer th' booty" |
| "Are you sure about this?" | "Be ye aye about this?" |
| "The money is in the house" | "Th' doubloons be in th' quarters" |

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/status` | System status overview |
| `GET` | `/api/media` | List cached media items |
| `GET` | `/api/jobs` | List translation jobs |
| `POST` | `/api/scan` | Trigger immediate scan |
| `POST` | `/api/translate` | Translate a specific SRT file |
| `POST` | `/api/preview` | Preview pirate translation |
| `GET` | `/api/settings` | Get current settings |
| `POST` | `/api/settings` | Save settings |
| `POST` | `/api/settings/test` | Test Sonarr/Radarr connection |
| `POST` | `/api/jobs/<id>/retry` | Retry a failed job |

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
python entrypoint.py

# Run tests
pytest tests/ -v
```

## License

GPLv3 - See [LICENSE](LICENSE) for details.
