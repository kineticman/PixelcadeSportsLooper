# SportsLooper Changelog

All notable changes to this project are documented here.

## [7.31.25.5a] – 2025-08-03
### Added
- Finalized support for all 16 leagues including MLS, WNBA, college sports, and European soccer leagues.
- Cleaned up README for clarity and renamed it to `SportsLooper_README.md`.
- Introduced `CHANGELOG.md` to track future updates.

### Changed
- Rebuilt release ZIP to include only clean files.
- Slimmed and reorganized config structure with `pixelcade_sports.ini`.

### Fixed
- Removed a lingering old README that was incorrectly packaged in earlier zips.

---

## [7.31.25.5] – 2025-08-03
### Added
- Support for full league list from ESPN and Pixelcade confirmed working.
- Logging now includes game relevance checks and ESPN API usage by league.

---

## [7.31.25.3] – 2025-07-31
### Added
- Tweaked event filtering and cooldown behavior.
- First attempt at full ESPN coverage before cleanup.

---

## [7.31.25.1] – 2025-07-30
### Added
- Initial baseline version with ESPN API polling and fallback weather.
- Integrated Pixelcade display rotation and logging per league.
- Proper NCAA Men’s Basketball API path enforced.

## [1.0.5] – 2025-08-03
### Changed
- Promoted project to semantic versioning (v1.0.5).
- Rearranged `pixelcade_sports.ini` for better readability and user-first customization.
  - `[league_toggles]`, `[environment]`, and `[service]` moved to the top.
  - Advanced sections like `[timing]`, `[network]`, `[circuit_breaker]` grouped under ADVANCED heading.
  - ESPN and Pixelcade mappings clearly marked as DO NOT MODIFY unless API changes.
- ZIP file renamed to reflect final versioning format.

### Notes
- This is now the officially tagged baseline for public release.
## v1.0.6 - 2025-08-07
- Fixed bug where display time calculation used all ESPN events instead of filtering to 24-hour window
- Now only games within ±24 hours are included in event count for display timing
- NFL, preseason, and all other leagues now calculate timing correctly
