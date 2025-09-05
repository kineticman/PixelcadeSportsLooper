# SportsLooper

**SportsLooper** is a Python script that displays sports scores, weather, stock prices, and a clock on a Pixelcade LED marquee. It runs as a background service on Windows or Raspberry Pi (Linux), fetching data from the ESPN API and a Pixelcade server. The project is configurable via an INI file and supports robust error handling for offline scenarios.

## Features
- **⚠ NEWS Module Status**: New in V1.1
- **Dynamic Display**: Cycles through modules (weather, clock, sports, stocks, news) on a Pixelcade LED marquee.
- **Sports Scores**: Fetches real-time scores from the ESPN API for 19 leagues (e.g., NFL, NBA, MLB, European soccer).
- **Configurable Modules**: Enable/disable modules and set display durations via `sportslooper.ini`.
- **Team Filtering**: Filter sports scores by specific teams per league (e.g., `NYY,BOS` for MLB).
- **Weather Display**: Shows weather for a specified ZIP code (e.g., `90210`).
- **Stock Prices**: Displays stock tickers (e.g., `AAPL,GOOGL`) with customizable duration.
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

### Installation on Windows
1. **Clone or Download**:
   - Place `sportslooper.py` and `sportslooper.ini` in `C:\Sportslooper`.
   - Ensure the directory is writable by the `SYSTEM` account:
     ```powershell
     icacls C:\SportsLooper /grant "SYSTEM:F" /T
     ```
2. **Configure `sportslooper.ini`**:
   - Edit `C:\SportsLooper\sportslooper.ini` (see [Configuration Highlights](#configuration-highlights)).
3. **Install Dependencies**:
   ```powershell
   cd C:\SportsLooper
   pip install requests tenacity pywin32
   ```
4. **Test Standalone**:
   ```powershell
   python sportslooper.py
   ```
5. **Install as Windows Service**:
   ```powershell
   python sportslooper.py install
   python sportslooper.py update --startup delayed-auto
   net start SportsLooper
   ```

### Installation on Raspberry Pi
1. **Install Python and Dependencies**:
   ```bash
   sudo apt update && sudo apt upgrade
   sudo apt install python3 python3-pip
   pip3 install requests tenacity
   ```
2. **Copy Files**:
   ```bash
   mkdir -p /home/pi/sportslooper
   cd /home/pi/sportslooper
   ```
3. **Configure `sportslooper.ini`**:
   - Edit `/home/pi/sportslooper/sportslooper.ini`.
4. **Test Standalone**:
   ```bash
   python3 sportslooper.py
   ```
5. **Create `systemd` Service**:
   ```bash
   sudo nano /etc/systemd/system/sportslooper.service
   ```
   Add:
   ```
   [Unit]
   Description=SportsLooper Service
   After=network.target

   [Service]
   ExecStart=/usr/bin/python3 /home/pi/sportslooper/sportslooper.py
   WorkingDirectory=/home/pi/sportslooper
   Restart=always
   User=pi
   Group=pi

   [Install]
   WantedBy=multi-user.target
   ```
   Then:
   ```bash
   sudo systemctl enable sportslooper
   sudo systemctl start sportslooper
   ```

## Configuration Highlights
The `sportslooper.ini` file controls behavior.

- **[pixelcade]**:
  - `pixelcade_url`: Pixelcade server URL.
  - `health_check_interval`: Seconds between retry cycles.
- **[weather]**:
  - `enabled`: true/false.
  - `zip_code`: ZIP code.
  - `duration`: Display time.
- **[sports]**:
  - `league_name`: Enable/disable leagues.
  - `league_name_teams`: Team filter.
- **[order]**:
  - `sequence`: Module order.

After editing, restart the service.

## Troubleshooting
- **Service Fails to Start**: Check Event Viewer (Windows) or `journalctl` (Pi).
- **No Logs**: Confirm file permissions.
- **Pixelcade Offline**: Retries every 30 seconds and logs to `fallback.log`.

## License
MIT License. See LICENSE for details.
