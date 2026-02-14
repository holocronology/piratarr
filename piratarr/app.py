"""Flask web application — REST API and web UI for Piratarr."""

import logging
import os
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template, request

from piratarr.arr_client import RadarrClient, SonarrClient, find_subtitle_files
from piratarr.database import (
    Config,
    MediaCache,
    TranslationJob,
    get_config,
    get_session,
    init_db,
    set_config,
)
from piratarr.scanner import scanner
from piratarr.subtitle import parse_srt, process_srt_file

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static"),
    )

    # Initialize database
    init_db()

    # Load settings from environment on first run
    _load_env_defaults()

    # Start background scanner
    scanner.start()

    # --- Web UI routes ---

    @app.route("/")
    def index():
        return render_template("index.html")

    # --- API routes ---

    @app.route("/api/status")
    def api_status():
        """Get system status overview."""
        session = get_session()
        try:
            total_media = session.query(MediaCache).count()
            with_subtitles = session.query(MediaCache).filter_by(has_subtitle=True).count()
            with_pirate = session.query(MediaCache).filter_by(has_pirate_subtitle=True).count()
            pending_jobs = session.query(TranslationJob).filter_by(status="pending").count()
            completed_jobs = session.query(TranslationJob).filter_by(status="completed").count()
            failed_jobs = session.query(TranslationJob).filter_by(status="failed").count()

            return jsonify(
                {
                    "scanner_running": scanner.is_running,
                    "is_scanning": scanner.is_scanning,
                    "last_scan": scanner.last_scan.isoformat() if scanner.last_scan else None,
                    "media": {
                        "total": total_media,
                        "with_subtitles": with_subtitles,
                        "with_pirate_subtitles": with_pirate,
                    },
                    "jobs": {
                        "pending": pending_jobs,
                        "completed": completed_jobs,
                        "failed": failed_jobs,
                    },
                }
            )
        finally:
            session.close()

    @app.route("/api/media")
    def api_media():
        """List all cached media items."""
        session = get_session()
        try:
            media_type = request.args.get("type")
            query = session.query(MediaCache)
            if media_type:
                query = query.filter_by(media_type=media_type)
            items = query.order_by(MediaCache.title).all()
            return jsonify([item.to_dict() for item in items])
        finally:
            session.close()

    @app.route("/api/jobs")
    def api_jobs():
        """List translation jobs."""
        session = get_session()
        try:
            status_filter = request.args.get("status")
            query = session.query(TranslationJob)
            if status_filter:
                query = query.filter_by(status=status_filter)
            jobs = query.order_by(TranslationJob.created_at.desc()).limit(100).all()
            return jsonify([job.to_dict() for job in jobs])
        finally:
            session.close()

    @app.route("/api/jobs/<int:job_id>/retry", methods=["POST"])
    def api_retry_job(job_id):
        """Retry a failed translation job."""
        session = get_session()
        try:
            job = session.query(TranslationJob).get(job_id)
            if not job:
                return jsonify({"error": "Job not found"}), 404
            if job.status != "failed":
                return jsonify({"error": "Only failed jobs can be retried"}), 400

            job.status = "pending"
            job.error_message = None
            session.commit()
            return jsonify({"message": "Job queued for retry", "job": job.to_dict()})
        finally:
            session.close()

    @app.route("/api/translate", methods=["POST"])
    def api_translate_file():
        """Manually trigger translation of a specific SRT file."""
        data = request.get_json()
        if not data or "path" not in data:
            return jsonify({"error": "Missing 'path' in request body"}), 400

        source_path = data["path"]
        if not os.path.exists(source_path):
            return jsonify({"error": "File not found"}), 404
        if not source_path.lower().endswith(".srt"):
            return jsonify({"error": "File must be an SRT file"}), 400

        session = get_session()
        try:
            job = TranslationJob(
                media_title=os.path.basename(source_path),
                media_type="manual",
                source_path=source_path,
                status="processing",
            )
            session.add(job)
            session.commit()

            try:
                output_path = process_srt_file(source_path)
                subtitle_file = parse_srt(open(source_path, "r", encoding="utf-8-sig").read())
                job.output_path = output_path
                job.status = "completed"
                job.subtitle_count = subtitle_file.count
                job.completed_at = datetime.now(timezone.utc)
                session.commit()
                return jsonify({"message": "Translation complete", "job": job.to_dict()})
            except Exception as e:
                job.status = "failed"
                job.error_message = str(e)
                session.commit()
                return jsonify({"error": f"Translation failed: {e}"}), 500
        finally:
            session.close()

    @app.route("/api/media/<int:media_id>/translate", methods=["POST"])
    def api_translate_media(media_id):
        """Translate subtitles for a specific media item."""
        session = get_session()
        try:
            cached = session.query(MediaCache).get(media_id)
            if not cached:
                return jsonify({"error": "Media not found"}), 404

            srt_files = find_subtitle_files(cached.path)
            if not srt_files:
                return jsonify({"error": "No subtitle files found for this media"}), 404

            jobs_created = 0
            for srt_path in srt_files:
                from piratarr.subtitle import get_pirate_srt_path
                pirate_path = get_pirate_srt_path(srt_path)
                if os.path.exists(pirate_path):
                    continue

                # Skip if job already pending/processing
                existing = (
                    session.query(TranslationJob)
                    .filter_by(source_path=srt_path)
                    .filter(TranslationJob.status.in_(["pending", "processing"]))
                    .first()
                )
                if existing:
                    continue

                job = TranslationJob(
                    media_title=cached.title,
                    media_type=cached.media_type,
                    source_path=srt_path,
                    status="pending",
                )
                session.add(job)
                jobs_created += 1

            session.commit()

            # Process queued jobs immediately
            if jobs_created > 0:
                from piratarr.scanner import scanner
                scanner._process_pending_jobs()
                # Update the media cache entry
                cached.has_pirate_subtitle = True
                session.commit()

            return jsonify({
                "message": f"Translated {jobs_created} subtitle file(s)" if jobs_created > 0 else "Already translated",
                "jobs_created": jobs_created,
            })
        finally:
            session.close()

    @app.route("/api/translate/batch", methods=["POST"])
    def api_translate_batch():
        """Translate subtitles for multiple media items at once."""
        data = request.get_json()
        if not data or "media_ids" not in data:
            return jsonify({"error": "Missing 'media_ids' in request body"}), 400

        media_ids = data["media_ids"]
        if not isinstance(media_ids, list) or not media_ids:
            return jsonify({"error": "'media_ids' must be a non-empty list"}), 400

        session = get_session()
        try:
            from piratarr.subtitle import get_pirate_srt_path

            total_jobs = 0
            items = session.query(MediaCache).filter(MediaCache.id.in_(media_ids)).all()

            for cached in items:
                srt_files = find_subtitle_files(cached.path)
                for srt_path in srt_files:
                    pirate_path = get_pirate_srt_path(srt_path)
                    if os.path.exists(pirate_path):
                        continue

                    existing = (
                        session.query(TranslationJob)
                        .filter_by(source_path=srt_path)
                        .filter(TranslationJob.status.in_(["pending", "processing"]))
                        .first()
                    )
                    if existing:
                        continue

                    job = TranslationJob(
                        media_title=cached.title,
                        media_type=cached.media_type,
                        source_path=srt_path,
                        status="pending",
                    )
                    session.add(job)
                    total_jobs += 1

            session.commit()

            if total_jobs > 0:
                scanner._process_pending_jobs()
                for cached in items:
                    cached.has_pirate_subtitle = True
                session.commit()

            return jsonify({
                "message": f"Translated {total_jobs} subtitle file(s)" if total_jobs > 0 else "All already translated",
                "jobs_created": total_jobs,
            })
        finally:
            session.close()

    @app.route("/api/scan", methods=["POST"])
    def api_trigger_scan():
        """Trigger an immediate media scan."""
        if scanner.is_scanning:
            return jsonify({"message": "Scan already in progress"}), 409
        summary = scanner.scan_now()
        return jsonify({"message": "Scan complete", "summary": summary})

    @app.route("/api/settings", methods=["GET"])
    def api_get_settings():
        """Get current application settings."""
        import json as _json

        settings = {
            "radarr_url": get_config("radarr_url", ""),
            "radarr_api_key": get_config("radarr_api_key", ""),
            "sonarr_url": get_config("sonarr_url", ""),
            "sonarr_api_key": get_config("sonarr_api_key", ""),
            "scan_interval": get_config("scan_interval", "3600"),
            "auto_translate": get_config("auto_translate", "false"),
        }
        # Path mappings stored as JSON string
        raw_mappings = get_config("path_mappings", "[]")
        try:
            settings["path_mappings"] = _json.loads(raw_mappings) if raw_mappings else []
        except (_json.JSONDecodeError, TypeError):
            settings["path_mappings"] = []
        # Mask API keys for display
        for key in ("radarr_api_key", "sonarr_api_key"):
            val = settings[key]
            if val and len(val) > 4:
                settings[key + "_masked"] = val[:4] + "*" * (len(val) - 4)
            else:
                settings[key + "_masked"] = ""
        return jsonify(settings)

    @app.route("/api/settings", methods=["POST"])
    def api_save_settings():
        """Save application settings."""
        import json as _json

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        allowed_keys = {"radarr_url", "radarr_api_key", "sonarr_url", "sonarr_api_key", "scan_interval", "auto_translate"}
        for key, value in data.items():
            if key in allowed_keys:
                set_config(key, value)

        # Path mappings are stored as a JSON string
        if "path_mappings" in data:
            mappings = data["path_mappings"]
            if isinstance(mappings, list):
                # Filter out empty entries
                mappings = [m for m in mappings if m.get("remote_path") and m.get("local_path")]
                set_config("path_mappings", _json.dumps(mappings))

        return jsonify({"message": "Settings saved"})

    @app.route("/api/settings/test", methods=["POST"])
    def api_test_connection():
        """Test connection to Sonarr or Radarr."""
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        service = data.get("service")
        url = data.get("url")
        api_key = data.get("api_key")

        if not all([service, url, api_key]):
            return jsonify({"error": "Missing service, url, or api_key"}), 400

        try:
            if service == "radarr":
                client = RadarrClient(url, api_key)
            elif service == "sonarr":
                client = SonarrClient(url, api_key)
            else:
                return jsonify({"error": "Unknown service"}), 400

            success = client.test_connection()
            return jsonify({"success": success})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)})

    @app.route("/api/preview", methods=["POST"])
    def api_preview_translation():
        """Preview pirate translation of sample text."""
        data = request.get_json()
        if not data or "text" not in data:
            return jsonify({"error": "Missing 'text' in request body"}), 400

        from piratarr.translator import translate

        translated = translate(data["text"], seed=42)
        return jsonify({"original": data["text"], "translated": translated})

    return app


def _load_env_defaults():
    """Load default settings from environment variables on first run."""
    env_map = {
        "RADARR_URL": "radarr_url",
        "RADARR_API_KEY": "radarr_api_key",
        "SONARR_URL": "sonarr_url",
        "SONARR_API_KEY": "sonarr_api_key",
        "SCAN_INTERVAL": "scan_interval",
        "AUTO_TRANSLATE": "auto_translate",
    }
    for env_var, config_key in env_map.items():
        env_val = os.environ.get(env_var)
        if env_val and not get_config(config_key):
            set_config(config_key, env_val)
