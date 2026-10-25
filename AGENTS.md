# AGENTS.md — adapting Skippy TV to another house

You are an AI coding agent asked to build "something like this" for a new user. This repo is a
**working reference for one specific house**, not a turnkey installer: IPs, entity IDs, app lists,
texts and the camera are hard-coded on purpose. Your job is to re-target it, not to run it as is.

## 0. What you need before touching anything

You must be able to run a shell on a machine **on the same LAN** as the TV box, with `adb`, `python3`,
`ffmpeg`, `curl` and Docker (locally or on a server you can reach). If you only have a chat window, stop
and tell the user what is missing.

Ask the user (or discover) and write down:

| Item | How to get it |
|---|---|
| TV box model + OS | `adb shell getprop ro.product.model`, `ro.build.version.release` (Fire TV: `ro.build.mktg.fireos`) |
| Network ADB enabled | Developer options → ADB/network debugging; the user must **accept the prompt on the TV** |
| Docker host for the cards server | any always-on box on the LAN |
| Home Assistant URL + long-lived token | HA profile → Security → Long-lived access tokens |
| Which lights, which one dims | `GET /api/states` or `/api/template` with `area_name()`; dimmable = `brightness` in `supported_color_modes` |
| Plex URL, token, machineIdentifier (optional) | `Preferences.xml` → `PlexOnlineToken`; `curl http://PLEX:32400/identity` |
| Camera (optional) | an RTSP camera behind **go2rtc**; the stream must be H.264 |
| Look and texts | node name/room, HUD texts, colors, which apps go in the dock |

Never commit tokens. They live in `cards/.env` on the Docker host (see `cards/.env.example`).
The signing keystore lives outside the repo (`KEYSTORE`, `KEYSTORE_PASS_FILE`).

## 1. Choose the path by OS version (this decides everything)

| Box | Path |
|---|---|
| Android TV / Google TV **10+** (Shield, Chromecast, most boxes) | Projectivy Launcher + `build-iconpack.sh` + cards via **Watch Next** (`Sync.java`) |
| Android **8-9** | same, but check the Projectivy version that still installs; Watch Next works from 8 |
| **Fire TV / Fire OS 6 (Android 7)** or anything where Projectivy will not install | custom launcher `Home.java` + `assets/home.html`; read the Fire TV section of `docs/ARCHITECTURE.md` first |

Do not try to replace the Amazon home screen on Fire OS 6: accessibility services, `set-home-activity` and
`pm disable-user` are all blocked (measured). The `Watch` service + a launcher icon is the ceiling there.

## 2. Files to change (search for these values)

- `192.168.2.46` (cards server), `192.168.2.102` (go2rtc), `192.168.2.25` (Home Assistant),
  `192.168.2.111` / `.140` (devices) — in `cards/`, `channel-app/src/`, `channel-app/assets/home.html`.
- `cards/app.py`: `LIGHTS` (ids, names, entity_ids, which one has `dim`), the climate entities in
  `card_status()`, `QUIPS` (personality lines), stream name `rua`.
- `channel-app/assets/home.html`: `DOCK` (banner + package of each favourite), `HIDE`, `THEMED`.
- `gen.py` → `APPS` (which banners to draw; logos from Simple Icons by slug); `build-iconpack.sh` → `C`
  (package/activity → banner map). Get real activities with
  `adb shell cmd package query-activities -a android.intent.action.MAIN -c android.intent.category.LEANBACK_LAUNCHER --brief`.
- `anim.py` / `gen.py`: HUD texts (`HUD_NODE`), colors (`CYAN`, `NAVY`), planet, etc.
- `channel-app/AndroidManifest.xml`: rename the package if this is a different product.

## 3. Order of work (each step verified before the next)

1. Render assets (`gen.py`, `anim.py`) and **look at them** (open the PNG/first frame). Fix logos with bad bounding boxes.
2. Cards server: `.env`, `docker compose up -d --build`, then `curl /feed.json` returns cards and the PNGs look right.
3. App: `channel-app/build.sh`, install, `adb shell dumpsys deviceidle whitelist +<package>` (Doze kills its network
   with the TV off — measured).
4. Launcher (Projectivy path): wallpaper and icon pack via the `am start` lines in `docs/ARCHITECTURE.md`;
   in Projectivy turn off *Custom icon color* and *Color override*, and leave only your app in Watch Next.
5. Bridge panel: open it, confirm the camera time stamp **moves** and its latency against a real clock.
6. Lights: test with the user in the room. Toggle one light, confirm the state in Home Assistant, put it back.

## 4. Rules that cost us real mistakes

- **Never press OK/arrows on a light card while testing navigation.** We switched a living-room light off
  by accident this way. Test navigation with screenshots only; test actions deliberately and restore state.
- A screenshot is the source of truth for "does it look good". Take one after every visual change
  (`adb exec-out screencap -p`), and compare two frames to prove video is moving.
- "It compiled" is not "it works": verify on the device (activity in front, logcat, go2rtc consumers).
- Measure before blaming: the camera clock vs the real clock, CPU with `top`, memory with `dumpsys meminfo`.
- `d8` (build-tools 34) breaks on non-static inner/anonymous classes; use `--min-api` = the device API.
- Amazon WebView: do not scale the page by `innerWidth` (it lies); the app sets the zoom.

## 5. Done means

Home screen shows the animated wallpaper, themed banners and live cards; a card opens the right content;
the Bridge panel shows the live camera in under ~1-2 s and the lights reflect Home Assistant; after a reboot
it comes back by itself (on Fire TV: within ~1.5 min). Write down what you changed in a doc for the user.
