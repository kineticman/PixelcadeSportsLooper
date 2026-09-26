# Changelog

## [Unreleased]
### Changed
- **Pixelcade USB root auto-detection**: recovery root resets now target the USB root hub the detected device is attached to, falling back to the configured `pixelcade.usb_root` only when no device is present, so recovery survives moving the marquee to a different port.

### Fixed
- **Blank marquee during sports tickers**: the looper now confirms pixelweb actually drew each sports ticker before waiting out that league's display window, and moves on after repeated failures instead of leaving the panel dark for a full minute when a scoreboard fetch fails. Configurable from the Pixelcade tab in the admin UI, or via `pixelcade.confirm_output_seconds` (`0` disables).
- **Weather widget never appearing**: pixelweb holds a new request while it cancels the previous widget (34% of weather requests took over 5s to be accepted, up to 21s), so the looper's 5s timeout fired almost every cycle. It then moved on immediately, cancelling the weather widget before it could draw. The weather request now allows 20s, and a read timeout is treated as a queued payload rather than a failure, so the widget keeps its display window either way.

### Added
- **Log rotation for the Pixelcade listener**: `deploy/logrotate-pixelcade.conf` caps `pixelweb-debug.log` at 100 MB with three compressed rotations, since the file otherwise grows unbounded.
- **Auto-recovery for a missing marquee**: after a failed USB power-on the kernel stops retrying enumeration and the panel stays dark until the cable is reseated. A watchdog thread now power-cycles the port the marquee was last seen on (the software equivalent of replugging it), escalating to a root-hub reset on alternate attempts, with backoff. Toggle and timings are in the Pixelcade tab of the admin UI.

### Fixed
- **Stale serial handle after a port move**: when the marquee re-enumerated under a new device name, pixelweb kept running while writing to the deleted old node, leaving the panel stuck on its startup logo. The container supervisor now restarts pixelweb when the device name changes, not just when no device is present. The auto-recovery watchdog also refreshes which port the marquee was last seen on, so its port reset follows a move.

---

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
