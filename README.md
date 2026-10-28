# SportsLooper

SportsLooper is a Python service for driving a Pixelcade or BitPixel LED marquee. It
cycles through same-day ESPN scoreboards, local weather, customizable clocks, and
other display modules while exposing a Flask admin UI for configuration and device
recovery.

The current runtime lives in [`app/`](app/) and is designed to run with Docker
Compose on Linux. It runs alongside Pixelcade's `pixelweb` listener and sends display
requests to the Pixelcade HTTP API.

## Features

- **Sports:** 19 ESPN leagues, including the NFL, NBA, NHL, MLB, college sports,
  MLS, major European soccer leagues, and the UEFA Champions League.
- **Team filtering:** Limit a league to specific team abbreviations, such as
  `NYY,BOS` for MLB.
- **Weather and clocks:** ZIP-code weather plus digital, word, retro-arcade, and
  character-themed clocks.
- **Optional modules:** Stocks, RSS news tickers, and 21 Pixelcade widgets for
  media servers, music services, calendars, fantasy sports, Formula 1, and more.
- **Admin UI:** Enable modules, reorder the display sequence, edit league filters,
  test Pixelcade connectivity, and send manual Pixelcade commands from one page.
- **Live updates:** Saved configuration is reloaded at the start of each module
  cycle, so most changes do not require a restart.
- **Marquee recovery:** Health checks, render confirmation, output-stall detection,
  and USB auto-recovery help recover from a blank or disconnected panel.

> OAuth-backed widgets require their accounts and credentials to be configured in
> Pixelcade Companion before SportsLooper can display them.

## Requirements

- A Linux host with Docker Engine and Docker Compose v2.
- A supported Pixelcade or BitPixel USB marquee.
- A matching Pixelcade Linux runtime in `pixelcade-runtime/`, including `pixelweb`
  and its assets. Compose mounts this directory into both services; it is not
  downloaded by the SportsLooper image.
- Network access from the host for ESPN's public API and any configured weather,
  news, or widget providers.

The Compose setup uses host networking because `pixelweb` must communicate with the
marquee over USB. The recovery controls also need access to `/dev` and `/sys`.

## Quick Start

```bash
git clone git@github.com:kineticman/PixelcadeSportsLooper.git
cd PixelcadeSportsLooper

# Put the Pixelcade Linux runtime in this directory first. It is intentionally
# ignored by Git because it contains the platform-specific binary and artwork.
test -x pixelcade-runtime/pixelweb

cp app/config.example.json app/config.json
docker compose up -d --build
docker compose logs -f sportslooper
```

Open `http://<host-ip>:6992` to use the admin UI. Pixelcade's `pixelweb` API defaults
to port `8080`; set the server URL on the Pixelcade tab if yours differs, then use
**Test** to verify the connection.

To stop the stack:

```bash
docker compose down
```

## How It Runs

`docker-compose.yml` starts two services with access to the host network:

- `pixelweb` runs the Pixelcade listener and restarts it if the USB device disappears
  or re-enumerates under a different device node.
- `sportslooper` runs the background display loop and the admin UI. It mounts the
  host's `/dev` and `/sys` trees so Pixelcade health checks and USB recovery can see
  the real hardware.

The looper waits for `/info` to report initialized LED hardware, displays the startup
banner, then cycles through `order.sequence` in `app/config.json`. A module must also
have `enabled: true` to display.

## Configuration

Start with [`app/config.example.json`](app/config.example.json):

```bash
cp app/config.example.json app/config.json
```

Use the admin UI for normal changes. Settings are written to your local
`app/config.json`, which Compose bind-mounts into the container. That file is ignored
by Git so machine-specific preferences and feed URLs do not appear in the repository.

The main sections are:

| Section | Purpose |
| --- | --- |
| `pixelcade` | Pixelcade URL, health checks, timing, output confirmation, and USB recovery |
| `order.sequence` | Modules to cycle through and their display order |
| `sports.leagues` | League toggles and optional team-abbreviation filters |
| `weather`, `clock` | Location, display time, and clock appearance |
| `stocks`, `news` | Optional stock ticker and RSS feed settings |
| Widget sections | Enable and set display duration for Pixelcade Companion widgets |

Default display timing is controlled by the module's `duration`. Sports use
`sports.seconds_per_game` for each matching game. `pixelcade.minimum_display_seconds`
keeps fast modules on screen for a usable minimum.

For marquee troubleshooting, the Pixelcade tab also exposes:

- `confirm_output_seconds`: Wait for `pixelweb` to write a frame before consuming the
  module's display window. Set to `0` to disable.
- `output_stall_seconds`: Move on when `pixelweb` stops drawing during a sports
  window.
- `auto_recovery`: Power-cycle the marquee's USB port after it disappears, using a
  configurable delay and retry interval.

Do not commit private feed URLs, account credentials, or other secrets to
`app/config.json`.

## Run Without Docker

Local development requires Python 3.9 or newer and a Pixelcade server reachable from
the host.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app/main.py
```

The admin UI is available at `http://127.0.0.1:6992`. USB recovery features depend on
the host's `/sys` layout and may require elevated privileges; the Docker setup is the
supported deployment path.

## Logging and Troubleshooting

- SportsLooper logs to `app/sportslooper.log` and stdout. The file rotates at 1 MB
  with five backups.
- `pixelcade-runtime/pixelweb-debug.log` is Pixelcade's own log. If it grows quickly,
  replace the placeholder path in the example, then install
  [`deploy/logrotate-pixelcade.conf`](deploy/logrotate-pixelcade.conf) as
  `/etc/logrotate.d/pixelcade`.
- If the admin UI is unreachable, run `docker compose ps` and
  `docker compose logs sportslooper`.
- If Pixelcade reports offline, check `pixelcade-runtime/pixelweb.log`, the configured
  server URL, and whether the marquee's USB device is present.
- If the marquee is blank, use the Pixelcade tab's connection and recovery controls.
  Avoid repeated root-hub resets until the simpler USB reconnect action has been
  tried.

Run the repository's basic syntax check after changing Python code:

```bash
python -m py_compile app/*.py
```

There is currently no automated test suite.

## Project Layout

```text
app/                    Current Docker runtime and admin UI
app/config.example.json Defaults for a new local configuration
app/config.json         Local runtime configuration (ignored by Git)
deploy/                 Host log-rotation configuration
docs/                   GitHub Pages landing page
pixelcade-runtime/      Local Pixelcade installation (ignored by Git)
prototype/              Local experiments (ignored by Git)
```

## License

No license file is currently included in this repository.
