# Changelog

## [1.3] - 2025-08-17
### Fixed
- **ESPN date rollover**: now recalculates the YYYYMMDD date each loop and logs changes, preventing stale schedules past midnight.

### Added
- Version constants `__version__ = "1.3"` and `__version_date__ = "2025-08-17"` inside `sportslooper.py`.

---

## [1.1] - 2025-08-15
### Added
- **News module**: new INI section and code path to fetch/display news items (toggleable like other modules).

### Changed
- Updated logging to use rotating file handler (`sportslooper.log`, 1 MB, 5 backups).
- Cleaned up service install/uninstall steps to be more reliable on Windows.
- Improved error handling around Pixelcade API health check.

### Fixed
- Resolved occasional crash during startup banner display.

---

## [1.0] - 2025-08-13
### Added
- Initial release of **SportsLooper**.
- Support for live sports (MLB, NBA, NHL, NFL, WNBA, NCAA, soccer leagues).
- Weather module (ZIP code–based).
- Stock ticker module.
- Windows service wrapper (`SportsLooperService`) with install/remove/start hooks.
- Basic README and INI configuration.
