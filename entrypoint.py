"""Piratarr application entrypoint."""

import os
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger("piratarr")


def main():
    port = int(os.environ.get("PIRATARR_PORT", "6969"))

    logger.info("Starting Piratarr v0.1.0 on port %d", port)
    logger.info("Config directory: %s", os.environ.get("PIRATARR_CONFIG_DIR", "/config"))

    from piratarr.app import create_app

    app = create_app()

    # Use gunicorn in production, fallback to Flask dev server
    try:
        from gunicorn.app.base import BaseApplication

        class PiratarrGunicorn(BaseApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()

            def load_config(self):
                for key, value in self.options.items():
                    if key in self.cfg.settings and value is not None:
                        self.cfg.set(key.lower(), value)

            def load(self):
                return self.application

        options = {
            "bind": f"0.0.0.0:{port}",
            "workers": 2,
            "threads": 4,
            "timeout": 120,
            "accesslog": "-",
            "errorlog": "-",
            "loglevel": "info",
        }
        PiratarrGunicorn(app, options).run()

    except ImportError:
        logger.warning("Gunicorn not available, using Flask development server")
        app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
