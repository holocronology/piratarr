#!/bin/sh
# Piratarr container entrypoint
# Ensures /config directory is writable, then starts the application.

CONFIG_DIR="${PIRATARR_CONFIG_DIR:-/config}"

# If running as root, fix permissions and re-exec as piratarr user
if [ "$(id -u)" = "0" ]; then
    mkdir -p "$CONFIG_DIR"
    chown piratarr:piratarr "$CONFIG_DIR"
    exec gosu piratarr python entrypoint.py
fi

# If running as non-root (e.g. user set --user), just start directly
exec python entrypoint.py
