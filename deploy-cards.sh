#!/bin/bash
# Publica o servidor skippy-cards no host Docker. Uso: ./deploy-cards.sh [ssh-host] [pasta-remota]
# O .env (tokens) já tem que existir na pasta remota: ver cards/.env.example.
set -e
P=$(cd "$(dirname "$0")" && pwd); HOST=${1:-h46}; DIR=${2:-/dados/dockers/skippy-cards}
ssh "$HOST" "mkdir -p $DIR/data && test -f $DIR/.env" || { echo "falta $DIR/.env no $HOST (copie cards/.env.example)"; exit 1; }
tar czf - -C "$P/cards" app.py quips.py plexw.py ponte.html Dockerfile docker-compose.yml wallpaper.jpg fonts \
  -C "$P" house.json | ssh "$HOST" "cd $DIR && tar xzf -"
ssh "$HOST" "cd $DIR && docker compose up -d --build 2>&1 | tail -1"
URL=$(python3 -c "import json;print(json.load(open('$P/house.json'))['server']['public_url'])")
for i in $(seq 1 30); do curl -sf -m 5 "$URL/health" >/dev/null && break; sleep 2; done
curl -s -m 60 "$URL/feed.json" | python3 -c "import json,sys;j=json.load(sys.stdin);print('cards:', [c['id'] for c in j['cards']])"
