# SportsLooper

**SportsLooper** is a Python script that displays sports scores, weather, stock prices, news, and a clock on a Pixelcade LED marquee. 
It runs as a background service on Windows or Raspberry Pi (Linux), fetching data from the ESPN API, RSS feeds, and a Pixelcade server. 
The project is configurable via an INI file and supports robust error handling for offline scenarios.

## Features
- **Dynamic Display**: Cycles through modules (weather, clock, sports, stocks, news) on a Pixelcade LED marquee.
- **Sports Scores**: Fetches real-time scores from the ESPN API for 19 leagues (e.g., NFL, NBA, MLB, European soccer).
- **Configurable Modules**: Enable/disable modules and set display durations via `sportslooper.ini`.
- **Team Filtering**: Filter sports scores by specific teams per league (e.g., `NYY,BOS` for MLB).
- **Weather Display**: Shows weather for a specified ZIP code (e.g., `43016`).
- **Stock Prices**: Displays stock tickers (e.g., `AAPL,GOOGL`) with customizable duration.
- **News Ticker**: Displays live news headlines via RSS feeds, with per-feed durations and optional total runtime cap.
- **Robust Error Handling**: Retries Pixelcade server connections (3 attempts, 2-second delays) every 30 seconds when offline.
- **Log Rotation**: Logs to `sportslooper.log` and `fallback.log` with 1 MB max size and 5 backups (~12 MB total).
- **Background Execution**: Runs as a Windows service (with delayed start option) or a `systemd` service on Raspberry Pi.
- **Debug Mode**: Detailed console output for troubleshooting when enabled.

## Installation

### Prerequisites
- **Python**: Python 3.9+.
- **Dependencies**:
  - Windows: `pip install requests tenacity pywin32`
  - Raspberry Pi: `pip3 install requests tenacity`
- **Pixelcade Server**: Running on `http://localhost:8080` (configurable).
- **Disk Space**: ~12 MB for logs.
- **Permissions**:
  - Windows: Administrator access for service installation.
  - Raspberry Pi: Write access to project directory for `pi` user.


## Configuration Highlights
The `sportslooper.ini` file controls behavior. Key settings:

- **[pixelcade]**:
  - `pixelcade_url`: Pixelcade server URL (default: `http://localhost:8080`).
  - `health_check_interval`: Seconds between retry cycles when Pixelcade is offline (default: `30`).
  - `health_check_timeout`: Timeout per health check attempt (default: `5`).

- **[weather]**:
  - `enabled`: Enable/disable weather (default: `true`).
  - `zip_code`: ZIP code (e.g., `90210`).
  - `duration`: Display time in seconds (default: `10`).

- **[sports]**:
  - `league_name`: Enable/disable leagues (e.g., `nfl = true`, `wnba = false`).
  - `league_name_teams`: Team filter (e.g., `mlb_teams = NYY,BOS`).
  - `seconds_per_game`: Display time per game (default: `4`).
  - `use_team_filter`: Apply team filters (default: `true`).

- **[clock]**, **[stocks]**, **[news]**:
  - `enabled`: Enable/disable module.
  - `duration` (clock, stocks): Display time in seconds.
  - `tickers` (stocks): Stock symbols (e.g., `AAPL,GOOGL`).
  - **News-specific**:
    - `rss_feeds`: Comma-separated RSS URLs.
    - `duration_per_feed`: Seconds to display each feed (default: `60`).
    - `max_total_runtime`: Max runtime in seconds (0 = unlimited, default: `0`).

- **[order]**:
  - `sequence`: Module order (e.g., `weather,clock,sports,stocks,news`).

- **[debug]**:
  - `debug_mode`: Console debug output (default: `false`).
  - `log_level`: Logging level (e.g., `INFO`, `DEBUG`).

**Note**: After editing `sportslooper.ini`, restart the service:
- Windows: `net stop SportsLooper && net start SportsLooper`
- Raspberry Pi: `sudo systemctl restart sportslooper`

## Troubleshooting
- **Service Fails to Start**: Check logs, Event Viewer (Windows), or `systemctl status sportslooper` (Pi).
- **No Logs**: Confirm file permissions on project directory.
- **Pixelcade Offline**: Retries 3 times, then every 30 seconds.
- **News Feeds Fail**: Verify RSS URLs are valid and accessible from the host.

## License
MIT License. See [LICENSE](LICENSE) for details.
