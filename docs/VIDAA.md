# Skippy Home on a Hisense VIDAA TV

VIDAA (Hisense's own OS, also on some Toshiba sets) is not Android: no ADB, no APK, no way to replace the
home screen, no file writes. What works, measured on a Hisense 55A60QUV (firmware `V0000.09.60L.Q0623`, 2026-10-30):

- the same Skippy Home as the Shield/Fire TV, as a **web page** opened by a **tile in the TV's app list**;
- a **bridge** on the Docker host that talks to the TV over its remote-control MQTT (port 36669):
  it opens the Skippy tile whenever the TV lands on VIDAA's home, and lets the page launch native apps
  (Netflix, YouTube, Plex…) and switch HDMI inputs;
- an **animated 4K background**: the page itself is capped at 1080p, but `<video>` goes to the hardware
  video plane, so a 3840x2160 loop behind the page is real 4K.

```
TV tile "Skippy" ──> http://<host>:8780/skippy.html   (vidaa/home.html, assets in sk/)
        page ──fetch──> bridge :8781 ──MQTT/TLS 36669──> TV   (apps, inputs, Home takeover)
        page ──fetch──> bridge /cards/* ──proxy──> skippy-cards (feed, quip, Plex; it has no CORS)
        page ──link───> skippy-cards /ponte  (camera + lights, Back returns to the home)
```

Everything is served by the Docker host; the TV only stores the tile. Measured cost: bridge 19 MB RAM,
~0 % CPU; the web server only works while the home is open (~16 MB per open, LAN).

## 1. Assets (once per room)

```bash
venv/bin/python -I gen.py $PWD "BRIDGE 03  ·  COZINHA  ·  NODE <tv-ip>"      # banners + wallpaper.jpg
mv dist/out/wallpaper.jpg dist/out/wallpaper-cozinha.jpg                       # deploy.sh picks wallpaper-<room>.jpg
SCALE=2 HUD_NODE="BRIDGE 03  ·  COZINHA  ·  NODE <tv-ip>" venv/bin/python -I anim.py $PWD | \
  ffmpeg -f rawvideo -pix_fmt rgb24 -s 3840x2160 -r 30 -i - -c:v libx264 -preset medium -crf 21 \
  -pix_fmt yuv420p -profile:v high -level 5.1 -movflags +faststart dist/out/wallpaper-4k-cozinha.mp4
```
`SCALE=2` renders natively at 3840x2160 (not an upscale): ~35 min on one core, ~3.6 GB RAM, 16 MB file.
No ffmpeg/cairo locally? Run both in a throwaway `python:3.12-slim` container with `libcairo2 ffmpeg`.

## 2. house.json

Add the TV to `devices` with a `vidaa` block (see `docs/HOUSE.md` for the other fields):
```json
{"ip": "192.168.2.246", "room": "cozinha", "bridge": "BRIDGE 03", "label": "COZINHA",
 "media_player": "media_player.hisense_…", "wallpaper": "dist/out/wallpaper-4k-cozinha.mp4",
 "vidaa": {"ssh": "dotpi", "dir": "/dados/dockers/tv4k", "web": "http://<host>:8780",
           "bridge": "http://<host>:8781", "tv4k": ""}}
```
`tv4k` = URL of an optional native-4K panel (first dock icon); empty = no icon.

## 3. Pair and create the tile (TV on, you in front of it)

```bash
vidaa/bridge/setup.sh                                   # downloads Sidee (pinned) + paho-mqtt; NOT committed
cd vidaa/bridge && TV_HOST=<tv-ip> SKIPPY_URL=http://<host>:8780/skippy.html python3 -I pair.py
```
The TV shows a 4-digit PIN; type it. Pairing uses [Sidee](https://github.com/Empi9245/Sidee) (MIT): its
dynamic credential profile `modern` is what this firmware accepts. Sidee ships the official remote app's
client certificate, so it is downloaded, never copied into this repo. The token lands in
`vidaa/bridge/sideehome/` (gitignored) and renews itself on the host.

## 4. Deploy

Docker host: `vidaa/docker-compose.yml` (web + bridge; set `TV_HOST`, `CARDS`, `SKIPPY_URL`), then:
```bash
vidaa/deploy.sh            # page (placeholders filled from house.json), assets, bridge; token copied once
```
It prints `pagina ok` and `ponte conectada na TV`. That is not the proof: press **Home** on the remote and
watch VIDAA's home get replaced by Skippy within ~3-5 s; open Netflix from the dock; open the camera and
press Back.

## What does NOT work (measured, do not repeat)

| Tried | Result |
|---|---|
| `hisense://debug` installer in the TV browser | address rejected on this firmware |
| `Hisense_installApp()` on a spoofed `vidaahub.com` | returns success, tile never appears |
| `HiUtils_createRequest` read/write of `websdk/Appinfo.json` | `client request permission check error, please check appconfig` |
| MQTT with the static `hisenseservice/multimqttservice` login | `rc=5 Not authorized` (Sidee's `modern` profile: `rc=0`) |
| Replacing VIDAA's home | impossible; the bridge's takeover is the workaround (VIDAA flashes ~1 s) |
| Web page above 1080p | capped at 1280x720 CSS @ dpr 1.5; only `<video>` reaches 4K |

## Traps

- With an app open the TV does **not** answer `gettvstate`; silence is not a disconnect. The bridge relies on
  the MQTT keepalive (`is_connected()`), otherwise it reconnects every 20 s.
- Sidee's `add_tile` check is strict about the URL and reported "not confirmed" while the tile was there.
  Look at the end of the TV's app list before repeating.
- Pages opened from the home must handle Back themselves (`keyCode` 8/461/10009 → `history.back()`);
  `window.close()` closes the whole tile.
- Never copy an old `session.json` over the host's: the refresh token rotates. `deploy.sh` only copies it once.
- The page is drawn at 1920x1080 and scaled with `zoom = innerWidth / 1920`.
- `ponte.html` only grabs Back in a plain browser; the Android app (`?native=1`) keeps its own handler.
