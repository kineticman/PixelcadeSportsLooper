# Changelog

## v1.1 (2025-08-16)
- Added **News module** with RSS feed support:
  - Configure multiple feeds via `[news] rss_feeds` in `sportslooper.ini`.
  - Options for `duration_per_feed` (per-feed display time) and `max_total_runtime` (limit total runtime).
  - Displays feeds using Pixelcade `/ticker` endpoint.
- Updated `sportslooper.ini` with full [news] block, consistent with other modules.
- Improved logging around module enable/disable decisions and News feed processing.

## v1.0 (2025-08-14)
- Initial public release of SportsLooper.
- Modules: Weather, Clock, Sports (19 ESPN leagues), Stocks.
- Team filtering and duration settings.
- Windows Service + Raspberry Pi `systemd` support.
- Log rotation, fallback logging, robust Pixelcade health checks.
