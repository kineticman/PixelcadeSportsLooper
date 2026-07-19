# Repository Guidelines

## Project Structure & Module Organization

SportsLooper is a Python application for driving a Pixelcade LED marquee. Current runtime code lives in `app/`: `main.py` starts logging, the background looper thread, and the Flask admin UI; `looper.py` contains module display logic and external API calls; `web.py` exposes config/status endpoints; `templates/index.html` is the admin page. Runtime settings are stored in `app/config.json`. Root-level legacy files such as `sportslooper.py`, `sportslooper.ini`, and `piVersion.py` are kept for earlier standalone/Raspberry Pi workflows. Public docs live in `docs/`.

## Build, Test, and Development Commands

- `python -m venv .venv && source .venv/bin/activate`: create and enter a local virtual environment.
- `pip install -r requirements.txt`: install Flask, Requests, and Tenacity.
- `python app/main.py`: run the looper plus web admin locally at `http://0.0.0.0:6992`.
- `docker compose up --build`: build and run the container with host networking and `app/config.json` mounted.
- `docker compose down`: stop the container.

Keep a Pixelcade server reachable at the configured `pixelcade_url` when testing display behavior.

## Coding Style & Naming Conventions

Use Python 3.9+ compatible code unless changing the Docker baseline. Follow the existing 4-space indentation, snake_case names, module-level constants in UPPER_CASE, and small helper functions prefixed with `_` for private implementation details. Prefer structured JSON access over string parsing for configuration. Keep logging messages actionable and use existing `logging` calls rather than `print`.

## Testing Guidelines

No automated test suite is currently committed. For changes, run at least `python -m py_compile app/*.py sportslooper.py piVersion.py` and manually exercise the affected path through `python app/main.py` or Docker. If adding tests, place them under `tests/`, name files `test_*.py`, and prefer mocking `requests.get` so ESPN, RSS, stock, weather, and Pixelcade calls are deterministic.

## Commit & Pull Request Guidelines

Recent history uses concise, imperative commit subjects such as `Add Docker + web admin UI; replace INI config with JSON` and `Update changelog with News in v1.1`. Keep commits focused on one behavior or documentation change. Pull requests should include a short summary, changed configuration keys if any, manual verification steps, and screenshots for visible admin UI changes. Link related issues when available.

## Security & Configuration Tips

Do not commit local secrets, private feed URLs, or machine-specific service credentials. Treat `app/config.json` as editable runtime configuration and document any new keys in the README when behavior changes.
