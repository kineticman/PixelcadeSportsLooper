# Changelog

## [1.3] - 2025-08-17
### Fixed
- ESPN date handling: refreshes the YYYYMMDD date each loop and logs date changes to avoid stale games around midnight rollover.
- Ensures at least one game's duration is used for league display to prevent zero-second flashes.

### Notes
- Version bumped in `piVersion.py` and `sportslooper.py` to 1.3.
