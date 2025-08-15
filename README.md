# SportsLooper

**SportsLooper** is a Python script that cycles sports scores, weather, stocks, and a clock on a Pixelcade LED marquee. It runs as a background service on Windows or Raspberry Pi, pulling live data from the ESPN API and your Pixelcade server. Configuration is done via `sportslooper.ini`, and the script includes robust error handling for offline scenarios.

## Features
- **Dynamic Display**: Cycles through weather, clock, sports, stocks, and news modules.
- **Sports Scores**: Fetches real-time scores from ESPN for 19 supported leagues.
- **Configurable**: Enable/disable modules, set durations, and filter teams via `sportslooper.ini`.
- **Weather**: Shows local weather for your ZIP code.
- **Stocks**: Displays chosen stock tickers with adjustable display time.
- **Error Handling**: Retries Pixelcade connections automatically when offline.
- **Logging**: Rotating logs for normal output (`sportslooper.log`) and offline events (`fallback.log`).
- **Service-Friendly**: Runs as a Windows service (delayed start supported) or Raspberry Pi `systemd` service.
- **Debug Mode**: Optional console output for troubleshooting.

## Prerequisites
- **Python**: 3.9 or newer  
- **Dependencies**:
  - Windows: `pip install requests tenacity pywin32`
  - Raspberry Pi: `pip3 install requests tenacity`
- **Pixelcade Server**: Running at `http://localhost:8080` (default, configurable)
- **Disk Space**: ~12 MB for logs
- **Permissions**:
  - Windows: Admin rights for service install
  - Pi: Write access to install directory

## Installation

### Windows
1. **Copy Files**  
   Place `sportslooper.py` and `sportslooper.ini` in a folder (e.g., `C:\SportsLooper`) and ensure `SYSTEM` has write access:
   ```powershell
   icacls C:\SportsLooper /grant "SYSTEM:F" /T
   ```

2. **Edit Config**  
   Adjust `sportslooper.ini` to your needs (see **Configuration Highlights**).

3. **Install Dependencies**  
   ```powershell
   cd C:\SportsLooper
   pip install requests tenacity pywin32
   ```

4. **Test Standalone**  
   ```powershell
   python sportslooper.py
   ```

5. **Install as Service**  
   ```powershell
   python sportslooper.py install
   python sportslooper.py update --startup delayed-auto
   net start SportsLooper
   ```

6. **Uninstall** (optional)  
   ```powershell
   net stop SportsLooper
   python sportslooper.py remove
   ```

### Raspberry Pi
1. **Prepare Pi OS**  
   ```bash
   sudo apt update && sudo apt upgrade
   sudo apt install python3 python3-pip
   pip3 install requests tenacity
   ```

2. **Copy Files**  
   ```bash
   mkdir -p /home/pi/sportslooper
   chown -R pi:pi /home/pi/sportslooper
   ```

3. **Edit Config**  
   Adjust `/home/pi/sportslooper/sportslooper.ini`.

4. **Test Standalone**  
   ```bash
   python3 sportslooper.py
   ```

5. **Create systemd Service**  
   `/etc/systemd/system/sportslooper.service`:
   ```
   [Unit]
   Description=SportsLooper Service
   After=network.target

   [Service]
   ExecStart=/usr/bin/python3 /home/pi/sportslooper/sportslooper.py
   WorkingDirectory=/home/pi/sportslooper
   Restart=always
   User=pi

   [Install]
   WantedBy=multi-user.target
   ```
   ```bash
   sudo systemctl enable sportslooper
   sudo systemctl start sportslooper
   ```

## Configuration Highlights
`sportslooper.ini` settings:

- **[pixelcade]**
  - `pixelcade_url` — server address (default: `http://localhost:8080`)
  - `health_check_interval` — retry interval when offline
  - `health_check_timeout` — timeout per attempt
- **[weather]**
  - `enabled` — true/false
  - `zip_code` — e.g., `43016`
  - `duration` — seconds to display
- **[sports]**
  - `<league>` — enable/disable (e.g., `nfl = true`)
  - `<league>_teams` — comma-separated abbreviations to filter
  - `seconds_per_game` — seconds per game
  - `use_team_filter` — true/false
- **[clock]**, **[stocks]**, **[news]**
  - `enabled` — true/false
  - `duration` — seconds to display
  - `tickers` (stocks only) — e.g., `AAPL,GOOGL`
- **[order]**
  - `sequence` — display order (e.g., `weather,clock,sports,stocks,news`)
- **[debug]**
  - `debug_mode` — true/false
  - `log_level` — DEBUG, INFO, etc.

Restart service after editing:
- Windows: `net stop SportsLooper && net start SportsLooper`
- Pi: `sudo systemctl restart sportslooper`

## Usage
- **Standalone**:  
  Windows → `python sportslooper.py`  
  Pi → `python3 sportslooper.py`
- **Service Start**:  
  Windows → `net start SportsLooper`  
  Pi → `sudo systemctl start sportslooper`
- **Logs**: Check `sportslooper.log` and `fallback.log` in the install directory

## Troubleshooting
- **Service won’t start**: Check permissions, config file path, and required Python modules.
- **No logs**: Confirm write permissions for service account.
- **Pixelcade offline**: Script retries automatically and logs to `fallback.log`.

## License
MIT — see [LICENSE](LICENSE)
