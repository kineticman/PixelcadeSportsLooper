---
title: Pixelcade SportsLooper
description: Sports scores, weather, clocks, and media widgets for Pixelcade LED marquees.
---

# Pixelcade SportsLooper

Pixelcade SportsLooper is a **Python service** that displays live sports scores,
weather, clocks, and optional media widgets on Pixelcade and BitPixel LED marquees.
It runs alongside Pixelcade's `pixelweb` listener and includes a web admin UI for
configuration, connection testing, and USB recovery.

## Features

- Same-day scores from 19 ESPN leagues, with optional team filters
- ZIP-code weather and customizable digital, word, and retro-arcade clocks
- Optional stocks, RSS news, and Pixelcade Companion widgets
- Drag-and-drop module ordering and live configuration updates
- Health checks, render confirmation, output-stall detection, and USB auto-recovery
- Docker Compose deployment with host networking for the USB-connected marquee

## Quick Start

Clone the repository, install a matching Pixelcade Linux runtime in
`pixelcade-runtime/`, and start the stack:

```bash
git clone https://github.com/kineticman/PixelcadeSportsLooper.git
cd PixelcadeSportsLooper
test -x pixelcade-runtime/pixelweb
cp app/config.example.json app/config.json
docker compose up -d --build
```

Open `http://<host-ip>:6992` to configure the looper. See the
[README](https://github.com/kineticman/PixelcadeSportsLooper/blob/main/README.md)
for prerequisites, local development, configuration, and troubleshooting.

## Links

- [Source Code on GitHub](https://github.com/kineticman/PixelcadeSportsLooper)
- [Issues](https://github.com/kineticman/PixelcadeSportsLooper/issues)

---

_Last updated: {{ site.time | date: "%B %d, %Y" }}_
