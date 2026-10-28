# Repository Guidelines

## Project Structure & Module Organization

SportsLooper is a Python application for driving a Pixelcade LED marquee. Runtime code lives in `app/`: `main.py` starts logging, the background looper thread, and the Flask admin UI; `looper.py` contains module display logic and external API calls; `web.py` exposes config/status endpoints; `templates/index.html` is the admin page. `app/config.example.json` is the tracked default configuration, while `app/config.json` is ignored local runtime state. Public docs live in `docs/`.

The admin UI at port `6992` is the normal configuration interface and writes to `app/config.json`. The Pixelcade `pixelweb` listener defaults to port `8080`.

## Build, Test, and Development Commands

- `python -m venv .venv && source .venv/bin/activate`: create and enter a local virtual environment.
- `python -m pip install -r requirements.txt`: install Flask, Requests, and Tenacity.
- `cp app/config.example.json app/config.json`: create the local runtime configuration.
- `python app/main.py`: run the looper plus web admin locally at `http://0.0.0.0:6992`.
- `docker compose up -d --build`: build and start the `pixelweb` and `sportslooper` services with host networking.
- `docker compose down`: stop both services.

Keep a Pixelcade server reachable at `pixelcade.url` in `app/config.json` when testing display behavior.

## Coding Style & Naming Conventions

Use Python 3.9+ compatible code unless changing the Docker baseline. Follow the existing 4-space indentation, snake_case names, module-level constants in UPPER_CASE, and small helper functions prefixed with `_` for private implementation details. Prefer structured JSON access over string parsing for configuration. Keep logging messages actionable and use existing `logging` calls rather than `print`.

## Testing Guidelines

No automated test suite is currently committed. For changes, run at least `python -m py_compile app/*.py` and manually exercise the affected path through `python app/main.py` or Docker. If adding tests, place them under `tests/`, name files `test_*.py`, and prefer mocking `requests.get` so ESPN, RSS, stock, weather, and Pixelcade calls are deterministic.

## Commit & Pull Request Guidelines

Use concise, imperative commit subjects. Keep commits focused on one behavior or documentation change. Pull requests should include a short summary, changed configuration keys if any, manual verification steps, and screenshots for visible admin UI changes. Link related issues when available.

## Security & Configuration Tips

Do not commit local secrets, private feed URLs, or machine-specific service credentials. Keep `app/config.json` local, mirror new defaults in `app/config.example.json`, and document new keys in the README when behavior changes.
