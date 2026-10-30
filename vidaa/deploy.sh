#!/bin/bash
# Publica a home Skippy da TV VIDAA no host Docker descrito no house.json (devices[].vidaa).
# Uso: vidaa/deploy.sh [ip-da-tv]   (sem argumento: a primeira TV com "vidaa")
# Pagina -> <dir>/app/skippy.html, assets -> <dir>/app/sk/, ponte -> <dir>/bridge/ (token remoto nunca e sobrescrito).
set -e
P=$(cd "$(dirname "$0")/.." && pwd)
read -r SSH DIR WEB BRIDGE TV4K SERVER TVIP < <(python3 - "$P/house.json" "$1" <<'PY'
import json, sys
h = json.load(open(sys.argv[1])); want = sys.argv[2] if len(sys.argv) > 2 else ''
d = next(d for d in h['devices'] if d.get('vidaa') and (not want or d['ip'] == want))
v = d['vidaa']
print(v['ssh'], v['dir'], v['web'], v['bridge'], v.get('tv4k') or '-', h['server']['public_url'], d['ip'])
PY
)
[ "$TV4K" = "-" ] && TV4K=
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/app/sk/banners"
sed -e "s|__BRIDGE__|$BRIDGE|g" -e "s|__SERVER__|$SERVER|g" -e "s|__TV4K__|$TV4K|g" "$P/vidaa/home.html" > "$T/app/skippy.html"
grep -q '__[A-Z0-9]*__' "$T/app/skippy.html" && { echo "placeholder sem valor"; exit 1; }
cp "$P"/fonts/*.ttf "$T/app/sk/"
if [ -d "$P/dist/out" ]; then
  cp "$P"/dist/out/banner-*.png "$T/app/sk/banners/"
  ROOM=$(python3 -c "import json;print(next(d['room'] for d in json.load(open('$P/house.json'))['devices'] if d['ip']=='$TVIP'))")
  [ -f "$P/dist/out/wallpaper-$ROOM.jpg" ] && cp "$P/dist/out/wallpaper-$ROOM.jpg" "$T/app/sk/wallpaper.jpg"   # gen.py <repo> "<HUD>" + renomear
  W=$(python3 -c "import json;print(next(d['wallpaper'] for d in json.load(open('$P/house.json'))['devices'] if d['ip']=='$TVIP'))")
  [ -f "$P/$W" ] && cp "$P/$W" "$T/app/sk/wall-4k.mp4"
else
  echo "aviso: sem dist/out (rode gen.py/anim.py); publicando so a pagina"
fi
tar czf - -C "$T" app | ssh "$SSH" "cd $DIR && tar xzf -"
tar czf - -C "$P/vidaa/bridge" --exclude=sideehome --exclude=__pycache__ . | ssh "$SSH" "mkdir -p $DIR/bridge && tar xzf - -C $DIR/bridge"
if ! ssh "$SSH" "test -f $DIR/bridge/sideehome/.sidee/session.json"; then
  [ -f "$P/vidaa/bridge/sideehome/.sidee/session.json" ] || { echo "falta parear: vidaa/bridge/pair.py"; exit 1; }
  tar czf - -C "$P/vidaa/bridge" sideehome | ssh "$SSH" "tar xzf - -C $DIR/bridge && chmod -R go-rwx $DIR/bridge/sideehome"
  rm -rf "$P/vidaa/bridge/sideehome"   # o token renova no host; copia local envelhecida invalidaria o de la
fi
ssh "$SSH" "cd $DIR && docker compose restart \$(docker compose config --services | grep -E 'bridge') >/dev/null"
curl -sf -m 5 -o /dev/null "$WEB/skippy.html" && echo "pagina ok: $WEB/skippy.html"
for i in $(seq 1 15); do curl -sf -m 3 "$BRIDGE/api/state" | grep -q '"connected": true' && { echo "ponte conectada na TV"; exit 0; }; sleep 2; done
echo "ponte NAO conectou (TV desligada? token?): docker logs do servico bridge"
