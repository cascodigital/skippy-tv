#!/bin/bash
# Deploys the skippy-cards server to the Docker host. Usage: ./deploy-cards.sh <ssh-host> <remote-dir>
# The .env (tokens) must already exist in the remote dir: see cards/.env.example.
set -e
[ $# -eq 2 ] || { echo "usage: $0 <ssh-host> <remote-dir>   (e.g. $0 docker-host /srv/skippy-cards)"; exit 1; }
P=$(cd "$(dirname "$0")" && pwd); HOST=$1; DIR=$2
[ -f "$P/house.json" ] || { echo "missing $P/house.json: cp house.example.json house.json and edit it (docs/HOUSE.md)"; exit 1; }
ssh "$HOST" "mkdir -p $DIR/data && test -f $DIR/.env" || { echo "falta $DIR/.env no $HOST (copie cards/.env.example)"; exit 1; }
tar czf - -C "$P/cards" app.py quips.py plexw.py ponte.html Dockerfile docker-compose.yml wallpaper.jpg fonts \
  -C "$P" house.json | ssh "$HOST" "cd $DIR && tar xzf -"
ssh "$HOST" "cd $DIR && docker compose up -d --build 2>&1 | tail -1"
URL=$(python3 -c "import json;print(json.load(open('$P/house.json'))['server']['public_url'])")
for i in $(seq 1 30); do curl -sf -m 5 "$URL/health" >/dev/null && break; sleep 2; done
curl -s -m 60 "$URL/feed.json" | python3 -c "import json,sys;j=json.load(sys.stdin);print('cards:', [c['id'] for c in j['cards']])"
