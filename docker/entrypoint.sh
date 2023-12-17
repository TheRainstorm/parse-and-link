#!/bin/bash

PUID=${PUID:-1000}
PGID=${PGID:-1000}

usermod -u $PUID myuser
groupmod -g $PGID mygroup
chown -R myuser:mygroup /parse-and-link

su myuser -c "python3 run_config.py -c /config.json" -m