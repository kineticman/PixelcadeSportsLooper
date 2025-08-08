# 🏟️ SportsLooper

**SportsLooper** is a lightweight Python service that fetches **live sports scores** from ESPN and displays them on a **Pixelcade LED marquee**. It supports multiple leagues and runs continuously as a background Windows service.

![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows-blue)
![Status](https://img.shields.io/badge/version-1.0.5-brightgreen)

---

## ⚙️ Features

- 🔴 Real-time display of **live scores** from ESPN
- ⚾ Supports **MLB**, **NHL**, **NFL**, **NBA**, **NCAAM**, **NCAAF**, **MLS**, etc.
- 🌦️ Cycles between live sports and **local weather**
- 🔁 Refreshes data every **10 minutes**
- 🪵 Built-in **logging** to track all activity and errors
- 🪛 Fully configurable via `pixelcade_sports.ini`
- 🖥️ Runs as a **Windows service**
- ✅ Zero cooldown: displays live sports content immediately

---

## 🧰 Prerequisites

- Windows 10 or later  
- Python 3.11+  
- [`Pixelcade.exe`](https://pixelcade.org/download/) must be running (this enables the `/image` API endpoint)  
- Pixelcade must be connected and configured properly

---

## 📂 Folder Contents

- `scores_service_main.py` – Core script that handles ESPN calls and Pixelcade output
- `pixelcade_sports.ini` – League toggles and display config
- `logs/` – Log files (ignored by Git)
- `CHANGELOG.md` – Version history

---

## 🪛 Setup Instructions

1. Install Python 3.11+
2. Extract the release zip (`SportsLooper_v1.0.5.zip`)
3. Edit `pixelcade_sports.ini` to enable desired leagues
4. Run script in debug mode to test:
   ```bash
   python scores_service_main.py debug
   ```

---

## 🧱 Windows Service Installation

1. Open **Command Prompt (Administrator)**  
2. Navigate to the project folder:
   ```cmd
   cd C:\Pixelcade\SportsLooper
   ```
3. Install the service:
   ```cmd
   python scores_service_main.py install
   ```
4. Start the service:
   ```cmd
   sc start PixelcadeSportsService
   ```

To uninstall:
```cmd
sc stop PixelcadeSportsService
python scores_service_main.py remove
```

---

## 🔧 Configuration

Edit `pixelcade_sports.ini` to control:

- Enabled leagues (`mlb=true`, `nba=false`, etc.)
- Display durations per league
- Refresh logic (every 10 minutes)

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).

---

## 💬 Questions?

Open an issue or message @kineticman.
