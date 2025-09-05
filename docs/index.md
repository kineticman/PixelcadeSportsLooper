---
title: Pixelcade SportsLooper
description: Sports and Weather Looper for Pixelcade LED marquees — cycles ESPN scores, weather, stocks, and news using a Python Windows/Raspberry Pi service.
---

# Pixelcade SportsLooper

Pixelcade SportsLooper is a **Python service** that displays live **sports scores, weather, stocks, and news** on Pixelcade LED marquees.  
It integrates with the ESPN API and runs as either a Windows service or on Linux (systemd).

![Pixelcade SportsLooper Demo](assets/demo.gif)

## Features
- Loops through multiple sports leagues (NFL, NBA, NHL, MLB, NCAA, Soccer, and more)
- Weather, stocks, and custom text modules
- Adjustable display durations via `pixelcade_sports.ini`
- Full logging of all display actions
- Runs headless — no user interaction required once started

## Installation
Clone and follow the instructions in the README:

```bash
git clone https://github.com/kineticman/PixelcadeSportsLooper.git
cd PixelcadeSportsLooper
```

See the [README](../README.md) for detailed setup instructions.

## Links
- [Source Code on GitHub](https://github.com/kineticman/PixelcadeSportsLooper)
- [Releases](https://github.com/kineticman/PixelcadeSportsLooper/releases)

---

_Last updated: {{ site.time | date: "%B %d, %Y" }}_
