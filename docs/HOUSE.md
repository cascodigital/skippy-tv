# house.json — everything that belongs to one house

The code reads every house-specific value from `house.json` at the repo root: the cards server loads it at
start (`HOUSE_JSON`, default `/app/house.json`), `channel-app/build.sh` bakes the URLs into the APK
(`Config.java` + `assets/home.html`) and picks the wallpapers. **Tokens never go here** — they live in
`cards/.env` on the Docker host (`HASS_TOKEN`, `PLEX_TOKEN`, see `cards/.env.example`).

Start from a draft: `HASS_URL=… HASS_TOKEN=… python3 tools/discover_ha.py > house.json` (read-only; it explains
every guess on stderr and leaves `TODO` where it cannot know).

| Key | Meaning | Required |
|---|---|---|
| `server.public_url` | Where the TV boxes reach the cards server (LAN IP of the Docker host + `:8099`). Baked into the APK. | yes |
| `hass.url` | Home Assistant base URL, seen **from the Docker host**. | yes |
| `plex.url`, `plex.machine_id` | Plex Media Server and its `machineIdentifier` (`curl PLEX:32400/identity`). Remove the Plex cards if you have no Plex. | optional |
| `camera.go2rtc` | go2rtc base URL. The live view needs an **H.264** stream. | optional |
| `camera.stream` | Stream name in `go2rtc.yaml` (here `rua`). | with camera |
| `camera.label`, `camera.title` | Text on the HUD (`AO VIVO // PÁTIO`) and the card title. | with camera |
| `camera.motion_entity` | `binary_sensor` that fires on motion. Avoid "person detection" entities that stick `on` (the Tapo one did). | with camera |
| `camera.windy_per_hour` | Above this many motion events per hour, motion stops being an alert and Skippy jokes about the wind instead. | no (15) |
| `door.entity`, `door.room` | A door/contact `binary_sensor` and the room name used in the lines ("a porta da *sala*"). | optional |
| `climate.*` | Indoor/outdoor temperature and humidity sensors, the `weather.*` entity and an `is_night` `binary_sensor`. | yes (card "Ponte") |
| `lights[]` | The light groups of the Bridge panel and the lights card. `id` (short slug, used by the lines), `name`, `entities` (one or more `light.*`, toggled together), `dimmable` (adds a brightness bar; use on single lights with brightness). **This is the allow-list**: the server refuses any other light. 3-5 groups fit the panel. | yes |
| `devices[]` | One entry per TV box: `ip` (fixed, set a DHCP reservation), `room`, `bridge` and `label` (HUD texts), `media_player` (HA entity of that TV, used by the lines), `wallpaper` (MP4 baked into the APK), `fire_tv: true` on Amazon devices. The server tells rooms apart by the requesting IP. | yes |
| `extras.laptop_open` | Optional boolean used by one joke. | no |

## What is still house-specific outside house.json

Deliberately left in code, because it is taste, not wiring:

- **Skippy's lines** (`cards/quips.py`), in Brazilian Portuguese, with the persona of Skippy (*Expeditionary Force*).
  A few reference light ids (`sala`, `quarto`, `cozinha`, `rua`) and rooms (`sala`, `quarto`); with other ids those
  specific lines simply never fire. Translate or rewrite freely — keep the priority numbers.
- **Dock candidates** (`DOCK_ALL` in `channel-app/assets/home.html`): the first installed package of each entry is
  used, so most boxes need no change; add your apps there.
- **Banners** (`gen.py` → `APPS`) and the HUD texts baked into the wallpaper (`anim.py`, `HUD_NODE`).
