#!/bin/bash

PUID=${PUID:-1000}
PGID=${PGID:-1000}

if [ `id -u abc` -ne $PUID ]; then
    usermod -u $PUID myuser
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