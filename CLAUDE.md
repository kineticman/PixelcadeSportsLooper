# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SportsLooper displays live sports scores, weather, clock, stocks, and news on a Pixelcade LED marquee. It runs in Docker on Ubuntu, talks to the Pixelcade server (`localhost:6992`) over the host network, and exposes a web admin UI on port 8080 for all configuration.

## Architecture

Two threads inside a single Docker container:

| Thread | File | Role |
|--------|------|------|
| Main (Flask) | `app/web.py` | Admin UI + REST API |
| Background | `app/looper.py` | Cycles through display modules |

Entry point is `app/main.py`, which starts the looper thread and then runs Flask on the main thread.

**Config** lives in `app/config.json` (volume-mounted so it persists across rebuilds). The looper re-reads it at the start of every full cycle — no restart needed after saving from the web UI.

**Shared state** between the two threads:
- `looper.config_lock` — `threading.Lock` held when reading/writing `config.json`
- `looper.status` / `looper.status_lock` — dict of live status (current module, pixelcade health, last ESPN cache refresh) written by looper, read by Flask's `/api/status`

### Looper flow

1. Wait for Pixelcade health check (`GET /text?t=health`) to succeed (retries every `health_check_interval` seconds)
2. Show startup banner
3. Loop forever: reload config, iterate `order.sequence`, call `display_module()` for each
4. Each module: health-check Pixelcade (3 retries × 2s), send one HTTP request, sleep for configured duration

### Pixelcade API endpoints used

| Module  | Endpoint               | Key params |
|---------|------------------------|------------|
| health  | `GET /text`            | `t=health`, `l=1`, `ledonly=true` |
| weather | `GET /weather`         | `location=<zip>`, `ledonly=true` |
| clock   | `GET /clock`           | `12h=true`, `showSeconds=true`, `color=green` |
| sports  | `GET /sports/<league>` | `ledonly=true`, optional `teams=` |
| stocks  | `GET /stocks`          | `tickers=`, `c=blue`, `s=9` |
| news    | `GET /ticker`          | `feed=<url>`, `newsTickerRefresh=<sec>` |

### Sports module

`_update_game_cache()` fetches ESPN's public API (`site.api.espn.com/apis/site/v2/sports`) once per 30 minutes. Team filtering is done locally (matching `competitions[0].competitors[].team.abbreviation`) and the `teams=` param is also forwarded to Pixelcade for its own filtering. Display time = `len(filtered_games) × seconds_per_game`.

## Running with Docker

```bash
# Build and start (detached)
docker compose up -d --build

# View logs
docker compose logs -f

# Stop
docker compose down
```

Web admin: `http://<server-ip>:6992`

## Running locally (no Docker)

```bash
pip install -r requirements.txt
cd app
python main.py
```

Requires Pixelcade running at the URL in `config.json`.

## Key files

- `app/main.py` — entry point, wires threads, signal handlers
- `app/looper.py` — all display logic, ESPN cache, shared `status` dict
- `app/web.py` — Flask routes (`GET/POST /api/config`, `GET /api/status`, `GET /`)
- `app/templates/index.html` — Bootstrap 5 single-page admin (vanilla JS, no framework)
- `app/config.json` — live config, volume-mounted; only file that should be edited at runtime
- `docker-compose.yml` — `network_mode: host` so `localhost:6992` reaches Pixelcade on the Ubuntu host

## Legacy files (do not use as base for new work)

- `sportslooper.py` — Windows-only version (imports `win32serviceutil` etc. at top level, crashes on Linux)
- `piVersion.py` — incomplete Linux version superseded by `app/`
- `sportslooper.ini` — superseded by `app/config.json`

## Installing Pixelcade on this Ubuntu x86_64 server

When ready to connect the LED marquee via USB:
- `pixelweb` binary: `linux_amd64` build from `github.com/alinke/pixelcade-linux-builds`
- Installer supports standalone mode (no gaming frontend required — it detects the absence of RetroPie)
- Default Pixelcade port is 8080; SportsLooper config defaults to 6992 — update `pixelcade.url` in the web admin to match whichever port Pixelcade actually uses
