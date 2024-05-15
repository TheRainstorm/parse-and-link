#!/bin/bash

PUID=${PUID:-0}
PGID=${PGID:-0}

if [ "$PUID" -eq 0 ]; then
    echo "run as root"
    if [ -n "$JELLYFIN_URL" ] && [ -n "$JELLYFIN_API_KEY" ]; then
        echo "Jellyfin URL is set to $JELLYFIN_URL"
        python3 run_config.py -c /config.json -m -j "$JELLYFIN_URL" -k "$JELLYFIN_API_KEY"
    else
        python3 run_config.py -c /config.json -m
    fi
    exit 0
fi

if [ `id -u abc` -ne $PUID ]; then
    usermod -u $PUID abc
fi
if [ `id -g abc` -ne $PGID ]; then
    groupmod -g $PGID abc
fi
chown -R abc:abc /parse-and-link

if [ -n "$JELLYFIN_URL" ] && [ -n "$JELLYFIN_API_KEY" ] ; then
    echo "Jellyfin URL is set to $JELLYFIN_URL"
    su abc -c "python3 run_config.py -c /config.json -m -j $JELLYFIN_URL -k $JELLYFIN_API_KEY"
else
    su abc -c "python3 run_config.py -c /config.json -m"
fi