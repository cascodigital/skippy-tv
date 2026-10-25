<div align="center">

# Skippy TV

**A sci-fi starship-bridge home screen for Android TV — wired to a real house.**

Animated space wallpaper · neon app banners · live Plex and Home Assistant cards ·
a live patio camera at ~1 s latency · house lights with dimmer · an AI with an attitude problem.

![Android TV](https://img.shields.io/badge/Android%20TV-7.1%2B-3DDC84?logo=android&logoColor=white)
![Fire TV](https://img.shields.io/badge/Fire%20TV-Fire%20OS%206-FF9900?logo=amazon&logoColor=white)
![NVIDIA Shield](https://img.shields.io/badge/NVIDIA%20Shield-1st%20gen-76B900?logo=nvidia&logoColor=white)
![Home Assistant](https://img.shields.io/badge/Home%20Assistant-REST-41BDF5?logo=homeassistant&logoColor=white)
![Plex](https://img.shields.io/badge/Plex-continue%20watching-EBAF00?logo=plex&logoColor=white)
![License: MIT](https://img.shields.io/badge/license-MIT-blue)

![Demo on the Fire TV](docs/screenshots/demo.gif)

<sub>Real capture from the bedroom Fire TV Stick (1080p, sped-up cuts): home, cards, the Bridge with the live camera, and the Konami hyperspace jump.
Full 50-second recording: <a href="docs/demo-firetv-1080p.mp4">docs/demo-firetv-1080p.mp4</a>.</sub>

</div>

> **Built for 4K TVs.** The UI is laid out at 1080p and scaled by the box; the living-room Shield renders it at native 3840×2160
> (its screenshot below is a 4K capture), the static wallpaper is rendered at 4K. The demo above is 1080p only because the
> Fire TV Stick records at 1080p.

## What it looks like

![NVIDIA Shield home, 4K](docs/screenshots/shield-home.jpg)
<sub>NVIDIA Shield (4K capture, downscaled): Skippy's line, HUD cards, the round **Plex orbit** widget (next episode, continue watching with a progress ring, new arrivals, your week) and the dock. A real alert, too: the living-room door had been open for 2 hours.</sub>

![Fire TV home](docs/screenshots/firetv-home.jpg)
<sub>Same launcher on the bedroom Fire TV Stick, with bedroom-aware lines.</sub>

| The Bridge: live camera + lights | Camera full screen |
|---|---|
| ![Bridge panel](docs/screenshots/bridge.jpg) | ![Camera](docs/screenshots/shield-camera-fullscreen.jpg) |

| Fire TV — all apps | The banners |
|---|---|
| ![All apps](docs/screenshots/firetv-all-apps.jpg) | ![Banners](docs/screenshots/banners.png) |

## Skippy talks (on screen, never out loud)

Skippy is the Elder AI from *Expeditionary Force*: brilliant, arrogant, stuck in a TV box. Every 15 s he reads
the house — Home Assistant, the patio camera's motion history, Plex, the clock — and picks a line — and knows which room is watching (living-room Shield or bedroom Fire TV):

> *"27 motion alarms in the last hour. Either a very indecisive burglar, or the wind."* &nbsp;·&nbsp;
> *"Living-room door open for 27 min. Is that an invitation or did you forget, monkey?"* &nbsp;·&nbsp;
> *"Kitchen lights on at 3 am. I know what you are about to do. So does the fridge."*

Red frame for alerts (real motion at the gate, door left open), gold for rare and dated lines (11:11, 13:37, Christmas,
Friday the 13th, a 1-in-120 legendary). Windy days don't count: the palm tree triggers the camera 30 times an hour,
so Skippy keeps score instead — *"Last hour: palm tree 28, burglars 0."* (Lines are in Brazilian Portuguese.)

### Easter eggs

| Konami code on the Bridge → *Protocolo Elder* | ◀◀◀ on the camera → *Modo Mira* | Konami on the Fire TV home → hyperspace |
|---|---|---|
| ![Protocolo Elder](docs/screenshots/egg-elder.jpg) | ![Modo Mira](docs/screenshots/egg-mira.jpg) | ![Hyperspace](docs/screenshots/egg-hyperspace.jpg) |

None of them touch the house: the planetary takeover is cancelled because *"the neighbour's Wi-Fi is too slow"*.

## Where it runs

| Device | Status | How it is themed |
|---|---|---|
| **NVIDIA Shield TV, 1st gen** (2015, Tegra X1) — Android TV 11, 4K — living room | ✅ tested daily | The Skippy launcher as the real system home (instant Home button). Projectivy + icon pack + *Watch Next* cards also supported as a lighter option |
| **Amazon Fire TV Stick 4K, 1st gen** (AFTMM) — Fire OS 6 / Android 7.1 — bedroom | ✅ tested daily | The same Skippy launcher; Amazon does not allow replacing its home, so a watcher brings Skippy back ~5 s after Home |
| Any other Android TV / Google TV (Chromecast with Google TV, Mi Box, TCL, Philips…) | ⚠️ should work, not tested | Same app, Android 7.1+; the dock picks whichever of its apps are installed |

The whole thing is plain Android APIs (Watch Next, `MediaCodec`, `WebView`), a small Python server and
Home Assistant's REST API — nothing Shield- or Amazon-specific except the workarounds documented in
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). If you try it on another box, an issue with the model
and what happened is very welcome.

## Want one for your house? Ask an AI agent

This is a reference build for one specific house, not an installer. Give an AI coding agent with shell and
`adb` access on your LAN (Claude Code, Codex, Cursor…) this repo and a prompt like:

> Read https://github.com/cascodigital/skippy-tv, starting with `AGENTS.md`. Build the same kind of
> home screen for my TV box (model: ___). My Home Assistant is at ___; I want these lights: ___ (this one
> dims: ___). Camera via go2rtc at ___ (or none). Plex at ___ (or none). Docker host: ___. Ask me for
> anything missing, never commit tokens, and show me a screenshot after every visual step.

`AGENTS.md` tells the agent which path fits the device (Projectivy on Android TV 10+, custom launcher on
Fire OS / older Android), what to change, in which order, and the traps we already measured.

## Pieces

```
.
├── gen.py              static wallpaper + 640x360 neon banners (Simple Icons → cyan glow HUD frame)
├── anim.py             animated wallpaper: raw RGB frames → ffmpeg (parallax stars, drifting nebula, radar, shooting star)
├── build-iconpack.sh   "Skippy Icon Pack" APK (ADW icon-pack format, no code) for Projectivy
├── cards/              skippy-cards: Python server (Docker) that renders the HUD cards and serves the Bridge panel
│   ├── app.py          /feed.json, /c/*.png, /ponte, /api/lights, POST /api/light (allow-list), /api/quip
│   ├── quips.py        Skippy's lines: reads the house (HA, Plex, clock) and picks a context-aware joke
│   ├── plexw.py        Plex orbit: now playing, continue, next episode, new arrivals, your week
│   └── ponte.html      Bridge panel UI (D-pad driven)
├── channel-app/        Android app dev.skippy.channel (plain Java, no Gradle)
│   ├── src/…/Sync.java     pulls the feed → Watch Next + preview channel (Android 8+)
│   ├── src/…/Main.java     card click trampoline (Projectivy rewrites the card intent package)
│   ├── src/…/Ponte.java    Bridge panel: transparent WebView over a SurfaceView
│   ├── src/…/LiveCam.java  MPEG-TS demuxer → MediaCodec (low-latency live camera)
│   ├── src/…/Home.java     the Skippy launcher (Shield + Fire TV): looping video wallpaper + assets/home.html
│   └── src/…/Watch.java    Fire TV: brings Home back when the Amazon home shows up
├── fonts/              Orbitron, Rajdhani (SIL OFL)
└── logos/              Simple Icons SVGs + a few drawn ones
```

Architecture, data flow and every device quirk we hit (all measured): [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Build

Toolchain without root or Android Studio: JDK 21, build-tools 34, `android-34.jar`
in `~/ai/tools/android-build/` (see the doc). Python 3.12 with `pillow numpy scipy cairosvg` in `./venv`.

```bash
python3 -m venv venv && venv/bin/pip install pillow numpy scipy cairosvg
venv/bin/python -I gen.py $PWD                       # dist/out/wallpaper.jpg + banners
venv/bin/python -I anim.py $PWD | ffmpeg -f rawvideo -pix_fmt rgb24 -s 1920x1080 -r 30 -i - \
  -c:v libx264 -preset slow -crf 19 -pix_fmt yuv420p dist/out/wallpaper-anim.mp4
HUD_NODE='BRIDGE 02  ·  QUARTO  ·  NODE 192.168.2.140' venv/bin/python -I anim.py $PWD | ffmpeg … dist/out/wallpaper-anim-quarto.mp4
./build-iconpack.sh                                  # dist/skippy-iconpack.apk
channel-app/build.sh                                 # dist/skippy-channel.apk
```

Signing key and password live **outside** the repo: `~/ai/keys/skippy.keystore` and
`~/ai/keys/skippy-keystore.pass` (override with `KEYSTORE` / `KEYSTORE_PASS_FILE`).
Everything generated goes to `dist/` (git-ignored).

## Deploy

```bash
# cards server (on the Docker host 192.168.2.46)
scp cards/{app.py,quips.py,ponte.html,Dockerfile,docker-compose.yml,wallpaper.jpg} h46:/dados/dockers/skippy-cards/
scp -r fonts h46:/dados/dockers/skippy-cards/
ssh h46 'cd /dados/dockers/skippy-cards && docker compose up -d --build'
# .env on the host only: PLEX_TOKEN, PLEX_MID, HASS_TOKEN, HASS_URL, PLEX_URL, PUBLIC_URL (see cards/.env.example)

# devices
adb -s 192.168.2.111:5555 install -r dist/skippy-channel.apk dist/skippy-iconpack.apk   # Shield
adb -s 192.168.2.140:5555 install -r dist/skippy-channel.apk                            # Fire TV
adb -s <device> shell dumpsys deviceidle whitelist +dev.skippy.channel                  # both: Doze would cut its network
adb -s 192.168.2.140:5555 shell appops set dev.skippy.channel GET_USAGE_STATS allow      # Fire TV only (Watch)
```

## Security notes

Built for a private home LAN. The cards server keeps the Home Assistant and Plex tokens
server-side and only exposes an **allow-list** of four light groups
(`POST /api/light`, anything else → 403) — but it has **no authentication**: anyone on the
LAN can toggle those four lights. Do not expose port 8099 to the internet.

## Credits

Fonts: Orbitron and Rajdhani (SIL Open Font License). Logos: [Simple Icons](https://simpleicons.org) (CC0);
brands belong to their owners. Launcher on the Shield: Projectivy Launcher by spocky.

## License

MIT — see [LICENSE](LICENSE).
