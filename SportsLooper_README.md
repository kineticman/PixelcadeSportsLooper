# SportsLooper for Pixelcade (v1.0.7)

This is the **official SportsLooper** package for displaying live sports scores on a Pixelcade LED marquee using ESPN’s API.

---

## ✅ Key Features

- Pulls **live game data** from ESPN for supported leagues (NFL, MLB, NBA, NHL, etc.)
- Filters to only display **games within ±24 hours**
- Optional **INI-configurable cap** on total display duration (`max_total_display_time`)
- League toggles and display timing fully configurable in `pixelcade_sports.ini`
- Automatic fallback to **weather display** if no sports are live
- Designed to run as a **Windows service** or via manual debug

---

## ⚙️ Configuration (INI)

Edit `pixelcade_sports.ini`:

```ini
[display]
seconds_per_game = 6
display_time_min = 15
display_time_max = 180
max_total_display_time = 120
refresh_interval = 60
```

> Display time per league = min(# of games × seconds_per_game, max_total_display_time)

---

## 🧪 Manual Testing

To test manually without the service:

```bash
python scores_service_main.py debug
```

---

## 🧱 Running as a Windows Service

1. Open **Command Prompt as Administrator**
2. From the install folder, run:

```cmd
python scores_service_main.py install
sc config PixelcadeSportsService start= delayed-auto
sc start PixelcadeSportsService
```

---

## 📁 Included Files

- `scores_service_main.py` — Main script (v1.0.7)
- `pixelcade_sports.ini` — Config file (timing + league toggles)
- `CHANGELOG.md` — Version history
- `SportsLooper_README.md` — This file

---

## 🔄 Version History

See `CHANGELOG.md` for detailed logs.

