# AGENTS.md — build Skippy TV for another house

You are an AI coding agent (Claude Code, Codex, Cursor…) asked to give a user "something like this".
This repo is a **working build for one real house**; the house is described in one file, `house.json`.
Your job is to produce a new `house.json`, adjust taste where the user wants, build, deploy and **prove it works
on the TV**. Read `docs/HOUSE.md` (the schema) and `docs/ARCHITECTURE.md` (how it works + every trap we measured)
before writing anything.

## 0. Preconditions — stop and tell the user if any is missing

- You run a shell on a machine **on the same LAN** as the TV box, with `adb`, `python3`, `ffmpeg`, `curl`,
  SSH to an always-on **Docker host**, and outbound internet (to fetch the JDK/build-tools once).
- The user can sit in front of the TV for two minutes (accept the ADB prompt, look at the result).
- Home Assistant reachable from the Docker host. Plex and a go2rtc camera are optional.

If you only have a chat window, say so and stop: this is not doable without a shell on the LAN.

## 1. Ask the human only what you cannot discover

Ask, in one message:
1. TV box model(s) and the room of each. Ask them to enable *Developer options → Network/ADB debugging* and to
   **accept the "Allow debugging" prompt on the TV** when you connect (`adb connect <ip>:5555`).
2. A Home Assistant **long-lived access token** (Profile → Security). Plex token only if they want Plex cards
   (`Preferences.xml` → `PlexOnlineToken`, or plex.tv). Never print tokens, never commit them.
3. Which lights matter (3-5 groups) and which one should dim; whether there is a camera in go2rtc.
4. Language and tone for the lines (the shipped ones are Brazilian Portuguese, sarcastic Skippy persona).

## 2. Discover the rest yourself

```bash
adb connect <tv-ip>:5555 && adb -s <tv-ip>:5555 shell getprop ro.product.model ro.build.version.release
adb -s <tv-ip>:5555 shell getprop ro.build.mktg.fireos          # non-empty = Fire TV
HASS_URL=http://<ha>:8123 HASS_TOKEN=<token> python3 tools/discover_ha.py > house.json   # read-only draft
```

Then edit `house.json`: resolve every `TODO`, keep only the lights the user wants, give each TV a fixed IP
(DHCP reservation) and the right `media_player`. Check every entity exists: `GET /api/states/<entity>`.

## 3. Pick the path by device (this decides what works)

| Device | What you get | Notes |
|---|---|---|
| Android TV / Google TV 8+ (Shield, Chromecast GTV, Mi Box…) | Skippy launcher as the **real home** (instant) | Android 11+: the manifest already has `<queries>`; set home with `cmd package set-home-activity dev.skippy.channel/.HomeAlias`. If another launcher has an accessibility service intercepting Home, turn it off. |
| Fire TV (Fire OS 6/7) | Skippy launcher, Amazon home for ~5 s after Home, then Skippy | Amazon blocks replacing its home (measured: accessibility, set-home and disable all refused). Needs `appops set dev.skippy.channel GET_USAGE_STATS allow`. |
| Hisense/Toshiba VIDAA (not Android) | Same home as a web page behind a tile; bridge on the Docker host takes over VIDAA's home ~3-5 s after Home | No ADB/APK. Follow `docs/VIDAA.md` (Sidee pairing with an on-screen PIN, `vidaa/deploy.sh`). |
| Android TV with Projectivy kept | Icon pack + cards in *Watch Next* | Lighter option, no live widgets. |

Both: `adb shell dumpsys deviceidle whitelist +dev.skippy.channel` (Doze cuts the app's network while the TV is off).

## 4. Build and deploy, in this order, verifying each step

1. **Assets**: `venv/bin/python -I gen.py $PWD` and `anim.py` (README → Build). Open the PNG and a video frame and
   *look*. Change `HUD_NODE` per room. Add banners for the user's apps in `gen.py` → `APPS`.
2. **Server**: create `.env` on the Docker host from `cards/.env.example` (chmod 600), then `./deploy-cards.sh <ssh-host> <dir>`.
   Pass: it prints a non-empty card list; `curl <server>/api/quip` returns a line; `/api/lights` matches HA.
3. **APK**: `channel-app/build.sh` (generates `Config.java` from `house.json`; signing key outside the repo,
   `KEYSTORE`/`KEYSTORE_PASS_FILE`). Install with `adb install -r`, then the permissions from step 3.
4. **On the TV** (the only proof that counts): `adb exec-out screencap -p` after each change and look at it.
   The camera must **move** (compare two frames, or the on-screen clock against the real one); cards must open the
   right Plex item; the Home button must land on Skippy (Fire TV: within ~5 s).
5. **Lights**: test with the user watching. Toggle one group from the Bridge panel, confirm in HA, put it back.

## 5. Rules that cost us real mistakes

- **Never press OK/arrows on a light while testing navigation** — we switched a living-room light off by accident.
  Test navigation with screenshots; test light actions deliberately and restore state.
- Do not wake or take over a TV someone is watching: check `dumpsys activity activities | grep mResumedActivity`
  first. Installing the APK does not interrupt other apps; opening the Home does.
- `adb` over Wi-Fi to Fire TVs drops to `offline` after bursts of commands; only a power cycle fixed it here.
- "It compiled" is not "it works". "The service started" is not "Home works": test the real Home key.
- Measure before blaming (CPU with `top`, camera latency against a clock, logcat). Hardware decode (`LiveCam`) is
  why the camera works on weak boxes; WebRTC in a WebView did not.
- `d8` from build-tools 34 crashes on non-static inner/anonymous classes; `--min-api` must be the device API.
- Amazon's WebView lies about `innerWidth` and boosts text in wide blocks; the CSS/zoom fixes are in place, keep them.

## 6. Done means

Animated wallpaper; Skippy's line above the cards; live cards (climate, camera, lights, Plex); the round Plex
widget; the Bridge panel with the live camera (< ~1-2 s) and working lights; Home lands on Skippy; it all comes
back by itself after a reboot. Leave the user a short doc of what you changed and how to roll back
(`set-home-activity` back to their old launcher).
