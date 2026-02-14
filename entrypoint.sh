#!/bin/sh
# Piratarr container entrypoint
# Handles PUID/PGID for proper file permissions, then starts the application.

CONFIG_DIR="${PIRATARR_CONFIG_DIR:-/config}"

# If running as root, adjust UID/GID and re-exec as piratarr user
if [ "$(id -u)" = "0" ]; then
    PUID="${PUID:-1000}"
    PGID="${PGID:-1000}"

    # Update the piratarr group/user to match requested IDs
    if [ "$(id -g piratarr)" != "$PGID" ]; then
        groupmod -o -g "$PGID" piratarr
    fi
    if [ "$(id -u piratarr)" != "$PUID" ]; then
        usermod -o -u "$PUID" piratarr
    fi

    echo "Starting Piratarr with UID=$(id -u piratarr) GID=$(id -g piratarr)"

    mkdir -p "$CONFIG_DIR"
    chown piratarr:piratarr "$CONFIG_DIR"
    exec gosu piratarr python entrypoint.py
fi

# If running as non-root (e.g. user set --user), just start directly
exec python entrypoint.py
