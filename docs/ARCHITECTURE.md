# Architecture and field notes

Everything below was measured on the real devices on 2026-10-25, not assumed.

## Hosts

| Host | Role |
|---|---|
| `192.168.2.46` (Orange Pi 5, Docker) | `skippy-cards` container, port 8099. Plex Media Server on 32400. |
| `192.168.2.102` (OptiPlex) | `go2rtc` for the street camera (Tapo C206), stream `rua`, API/UI on 1984. |
| `192.168.2.25` | Home Assistant. |
| `192.168.2.111` | NVIDIA Shield, living room. |
| `192.168.2.140` | Fire TV Stick 4K (AFTMM), bedroom. |

## Data flow

```
Plex (/hubs/continueWatching/items, recentlyAdded) ─┐
Home Assistant (/api/states, /api/services/light) ──┼─► skippy-cards (.46:8099) ──► /feed.json + /c/*.png
go2rtc (/api/frame.jpeg?src=rua) ───────────────────┘          │                       │
                                                                │ /ponte, /api/lights   │
                                                                ▼                       ▼
                                                    Ponte (WebView UI)      Sync.java (Shield) → Watch Next
                                                                            home.html (Fire TV launcher)
go2rtc /api/stream.ts?src=rua&video=h264 ──► LiveCam.java (TS demux → MediaCodec → SurfaceView)
```

- `skippy-cards` renders cards in a **background thread** every 4 min (a cold render takes ~16 s:
  Plex image transcodes + camera snapshot) and always answers `/feed.json` from cache (~30 ms).
  A light action resets the timer so the lights card redraws right away.
- Card art: Plex backdrop graded to navy/cyan, the show's transparent **clearLogo**, episode line,
  cyan progress bar, cut-corner HUD frame with scanlines.
- Lights allow-list: `sala` = `light.luz_da_sala` (dimmable, `brightness_pct`), `quarto` = `light.luz_quarto`,
  `cozinha` = the three kitchen relays together, `rua` = `light.luzes_do_patio` (the patio group).

## Shield (Android TV 11)

- Launcher: Projectivy 4.72 (Premium) with the animated MP4 as wallpaper and the Skippy icon pack.
- Cards above the dock: Projectivy only puts **Watch Next** above the dock, so `Sync.java` publishes the
  feed both to Watch Next and to a preview channel (the channel is hidden in Projectivy). In Projectivy's
  Watch Next settings every other app is unticked, so only Skippy cards show.
- **Card click**: Projectivy rewrites the intent's package to the card's owner app, so every card opens
  `dev.skippy.channel/.Main` with `S.go=<url>` + `S.pkg=<app>` and `Main` forwards it.
  Plex opens the exact episode with `https://watch.plex.tv/show/<slug>/season/N/episode/N`
  (`/movie/<slug>` for films); `plex://server://…` only opens Plex home.
- Applying things without touching the remote:
  - wallpaper: `am start -a android.intent.action.VIEW -t video/mp4 -d content://media/external/video/media/<id> -n com.spocky.projengmenu/.ui.launcherActivities.SetBackgroundActivity --grant-read-uri-permission`
  - icon pack: `am start -a tv.projectivy.APPLY_ICONPACK -n com.spocky.projengmenu/.ui.launcherActivities.ApplyIconPackActivity` + OK
- Projectivy settings that matter: Cards → *Custom icon color* = none (otherwise it tints the banners),
  *Color override* = none; program cards *Show label* off.

## Live camera: why a hand-made player

| Tried on the Shield | Result |
|---|---|
| go2rtc WebRTC/MSE inside the WebView | ~115 % CPU (software decode), freezes when RAM is short; MSE already broken since Chrome 154 |
| `MediaPlayer` + RTSP | native NuPlayer crash |
| `MediaPlayer` + HLS (go2rtc serves fMP4 HLS) | error `-1004` |
| `MediaPlayer` + MPEG-TS | works, but ~7 s of fixed buffering |
| **`LiveCam`: TS demux → `MediaCodec`, render immediately** | **~1 s (the camera's own delay), 7-20 % CPU** |

The camera's on-screen clock was compared with the real clock to measure latency; the camera clock itself
was verified against a go2rtc JPEG snapshot. After 3 failures `LiveCam` gives up and the page falls back to
go2rtc's WebRTC player in an iframe (go2rtc's websocket only accepts its own origin, hence the iframe).

Bridge UI: the WebView is transparent; the page cuts a hole matching the panel's clipped corners
(`clip-path` with `evenodd`) and tells the app where the video goes with `Skippy.video(x, y, w, h)`
(fractions of the screen; full screen = `0,0,1,1`). Leaving the panel finishes the activity, so go2rtc
drops to 0 consumers.

Remote control: ▲▼ move between lights, OK toggles, the living-room dimmer is a **separate bar** under its
card (◀▶, 10 % steps), ◀ on any light goes to the camera, OK on the camera = full screen, Back leaves.
(The first version had the dimmer on the card itself; ◀ then OK switched the light off by accident.)

## Fire TV Stick 4K (Fire OS 6.7.1.1 = Android 7.1.2, API 25)

- Projectivy 4.72 requires Android 10, preview channels need Android 8 → a custom launcher (`Home.java`):
  `MediaPlayer` looping `assets/wallpaper.mp4` on a SurfaceView + `assets/home.html` in a transparent WebView.
  JS bridge `Launcher.apps()/launch()/open()`; app banners come from the system or from the theme.
- **The Home button cannot be taken over cleanly.** All measured:
  - third-party accessibility service (Projectivy's method): never bound by Fire OS (`settings put` is
    ignored; a value written with `content insert` sticks but the service is not bound) — the same service
    binds instantly on the Shield;
  - `cmd package set-home-activity`: says Success, Amazon stays home (priority 950);
  - `pm disable-user com.amazon.tv.launcher`: `Cannot disable a protected package`;
  - the shell cannot even toggle components of our own app (`Shell cannot change component state`) —
    the app enables its own components.
- What ships: **`Watch.java`**, a foreground service that reads `UsageStatsManager` events every 400 ms.
  Fire OS publishes the "moved to foreground" event ~1-1.5 s late, so it scans a 5 s window and tracks the
  newest event seen. When `com.amazon.tv.launcher/.ui.HomeActivity_vNext` comes forward it starts `Home`.
  Android 7 blocks background activity starts for 5 s after a Home press → in practice: Home → Amazon for
  ~5 s → Skippy. 4 relaunches in 5 s = loop → pauses 5 min. The *Amazon screen* tile pauses it 60 s.
- Boot: Fire OS does not record its own home in usage stats at boot and delivers `BOOT_COMPLETED` late;
  `Watch` opens Skippy 8 s after it. Measured: Skippy up ~1.5 min after power-on.
- Fallback: a "Skippy" banner in the Amazon app row (`FireIcon` alias; disabled in the manifest and enabled
  by the app itself only on `AFT*` models, so it does not duplicate on the Shield).
- Settings: the main settings menu lives inside the Amazon launcher (`com.amazon.tv.launcher/.ui.SettingsActivity`,
  what the dock *Ajustes* opens). Standalone screens that open from outside: Network, Applications,
  Controllers & Bluetooth, My Fire TV (`com.amazon.tv.settings.v2/.tv.*`). Display & Sounds, Preferences,
  Accessibility and Account require `com.amazon.tv.permission.LAUNCHER_SETTINGS` (signature|amazon).
- Amazon WebView 118 quirks: `setInitialScale(1)` means 1 % zoom; without it the page renders at 2×.
  The app sets `setInitialScale(100 * screenWidth / 1920)`. `innerWidth` lies (2201 on a 1920 screen),
  `visualViewport.width` is right — never scale the page by `innerWidth`.

## Both devices

- **Doze cuts the app's network while the TV is off** (`dumpsys netpolicy`: `REJECT_ALL`), so the feed sync
  timed out only inside the app while the shell could connect. Fix (persists across reboots, not across a
  clean reinstall): `adb shell dumpsys deviceidle whitelist +dev.skippy.channel`.

## Skippy's mouth (screen only, never sound)

`cards/quips.py` reads the house every 15 s (all Home Assistant states, one hour of street-motion history,
Plex sessions, the clock) and turns it into one-liners with a priority. `GET /api/quip` returns
`{text, mood}` (`normal` cyan, `alerta` red, `rara` gold). Used by the Bridge panel ("TRANSMISSÃO",
typed letter by letter every 20 s), the Fire TV home (line above the cards, every 30 s) and the
"Ponte // Sala" card (its frame turns red/gold with the mood).

- Priority bands: live street motion (100, but only if it is not a windy day — the Tapo fires 30+ times
  an hour when the palm tree moves, so then it jokes about the palm tree instead), date eggs (90-95),
  door open > 20 min (85), Plex playing/paused (80), 1-5 am (75), lights/climate/weekday (40-65),
  personality lines (10). Below 85 it mixes the hottest topic, another real fact and personality, and
  always picks the line said longest ago.
- `binary_sensor.tapo_c206_person_detection` sticks at `on` (measured): the code uses `motion_alarm`.
- The cards loop re-renders right away when motion or the door changes (checked every 20 s), not only
  every 4 min. The camera card gets a red "MOVIMENTO NA RUA" strip, or a "último movimento há N min" tag.

### Easter eggs
- **Konami code** (↑↑↓↓←→←→) on the Bridge panel: *Protocolo Elder* — red alarm, fake planetary takeover
  typed out, then "não toquei em nada". On the Fire TV home: a hyperspace jump. Screen only; nothing in
  the house is touched.
- **◀◀◀ on the camera** (Bridge panel): *Modo Mira* — the live camera goes full screen with a rotating
  reticle and a target box that "classifies" made-up threats (palm tree, the neighbour's cat…).
- 3 min without touching the remote on the Bridge panel: Skippy complains; the next key, he welcomes you back.
- 1-in-120 legendary golden lines; 11:11, 13:37, midnight, Christmas, New Year, Friday the 13th.
- Test without a remote: `/ponte?egg=elder`, `/ponte?egg=mira`.

## Build gotchas

- No Gradle: `aapt2 compile/link` → `javac -source 8 -target 8` (+ `core-lambda-stubs.jar` on the bootclasspath) → `d8` → `zipalign` → `apksigner`.
- `d8` from build-tools 34 crashes (`NullPointerException … String.length()`) on **non-static inner and
  anonymous classes** → use static nested classes, top-level classes or lambdas.
- `d8 --min-api 25`: the default dex 038 does not load on Android 7 (`Unrecognized version number … 0 3 8`).
- The cards Docker image copies its files (no bind mount): rebuild on every change.
