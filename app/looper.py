import requests
import time
import logging
import os
import json
import glob
import threading
from datetime import datetime, timedelta

import tenacity
from tenacity import retry, stop_after_attempt, wait_fixed

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, 'config.json')

# Shared state read by web.py for the status endpoint
status = {
    'current_module': None,
    'pixelcade_healthy': False,
    'last_cache_refresh': None,
    'running': False,
}
status_lock = threading.Lock()
config_lock = threading.Lock()

SUPPORTED_LEAGUES = {
    'nfl':                      'football/nfl',
    'nba':                      'basketball/nba',
    'nhl':                      'hockey/nhl',
    'mlb':                      'baseball/mlb',
    'wnba':                     'basketball/wnba',
    'eng.1':                    'soccer/eng.1',
    'esp.1':                    'soccer/esp.1',
    'ger.1':                    'soccer/ger.1',
    'ita.1':                    'soccer/ita.1',
    'fra.1':                    'soccer/fra.1',
    'por.1':                    'soccer/por.1',
    'ned.1':                    'soccer/ned.1',
    'mex.1':                    'soccer/mex.1',
    'usa.1':                    'soccer/usa.1',
    'uefa.champions':           'soccer/uefa.champions',
    'college-football':         'football/college-football',
    'mens-college-basketball':  'basketball/mens-college-basketball',
    'womens-college-basketball':'basketball/womens-college-basketball',
    'college-baseball':         'baseball/college-baseball',
}

ESPN_BASE_URL = 'https://site.api.espn.com/apis/site/v2/sports'

PIXELCADE_WIDGET_MODULES = {
    'youtube': {'endpoint': 'youtube', 'default_duration': 10},
    'calendar': {'endpoint': 'calendar', 'default_duration': 10},
    'spotify': {'endpoint': 'spotify', 'default_duration': 300},
    'lastfm': {'endpoint': 'lastfm', 'default_duration': 300},
    'plex': {'endpoint': 'plex', 'default_duration': 300},
    'yahoofantasy': {'endpoint': 'yahoofantasy', 'default_duration': 60},
    'netflix': {'endpoint': 'netflix', 'default_duration': 10},
    'worldclock': {'endpoint': 'worldclock', 'default_duration': 10},
    'commute': {'endpoint': 'commute', 'default_duration': 10},
    'horoscope': {'endpoint': 'horoscope', 'default_duration': 10},
    'lastgame': {'endpoint': 'lastgame', 'default_duration': 5},
    'whattowatch': {'endpoint': 'whattowatch', 'default_duration': 60},
    'mediaserver': {'endpoint': 'mediaserver', 'default_duration': 300},
    'trivia': {'endpoint': 'trivia', 'default_duration': 30},
    'twitch': {'endpoint': 'twitch', 'default_duration': 60},
    'countdown': {'endpoint': 'countdown', 'default_duration': 30},
    'dayinretro': {'endpoint': 'dayinretro', 'default_duration': 30},
    'retroachievements': {'endpoint': 'retroachievements', 'default_duration': 30},
    'earthquake': {'endpoint': 'earthquake', 'default_duration': 30},
    'f1': {'endpoint': 'f1', 'default_duration': 30},
    'flighttracker': {'endpoint': 'flighttracker', 'default_duration': 30},
}

game_cache = {}
cache_expiry = datetime.now()


def load_config():
    with config_lock:
        with open(CONFIG_PATH) as f:
            return json.load(f)


@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def _pixelcade_health_request(pixelcade_url, timeout):
    resp = requests.get(
        f"{pixelcade_url}/info",
        timeout=timeout,
    )
    resp.raise_for_status()
    info = resp.json()
    if not info.get('ledActive') or not info.get('hardwareID') or not info.get('firmwareVersion'):
        raise requests.RequestException('Pixelcade LED hardware is not initialized')
    if not _serial_device_present():
        raise requests.RequestException('Pixelcade serial device is not present')


def _serial_device_present():
    for root in ('/host-dev', '/dev'):
        if not os.path.isdir(root):
            continue
        for pattern in ('ttyACM*', 'ttyUSB*'):
            if glob.glob(os.path.join(root, pattern)):
                return True
    return False


def check_pixelcade_health(pixelcade_url, timeout):
    """Returns True if healthy, raises tenacity.RetryError / RequestException if not."""
    _pixelcade_health_request(pixelcade_url, timeout)
    return True


def _sleep(seconds, stop_event):
    """Sleep in 1-second ticks; returns True if stop was requested."""
    for _ in range(max(1, int(seconds))):
        if stop_event.is_set():
            return True
        time.sleep(1)
    return False


def _fetch_espn_games(league, date):
    try:
        url = f"{ESPN_BASE_URL}/{SUPPORTED_LEAGUES[league]}/scoreboard?dates={date}"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        return resp.json().get('events', [])
    except requests.RequestException as e:
        logging.error(f"ESPN API error for {league}: {e}")
        return game_cache.get(league, [])


def _update_game_cache(cfg, date):
    global game_cache, cache_expiry
    if datetime.now() < cache_expiry:
        return
    leagues_cfg = cfg.get('sports', {}).get('leagues', {})
    enabled = [l for l in SUPPORTED_LEAGUES if leagues_cfg.get(l, {}).get('enabled', False)]
    game_cache = {l: _fetch_espn_games(l, date) for l in enabled}
    cache_expiry = datetime.now() + timedelta(minutes=30)
    with status_lock:
        status['last_cache_refresh'] = datetime.now().isoformat()
    logging.info(f"ESPN cache updated: {len(game_cache)} leagues")


def _display_weather(cfg, pixelcade_url, stop_event):
    mod = cfg.get('weather', {})
    zip_code = mod.get('zip_code', '').strip()
    if not zip_code:
        logging.warning("Weather module: zip_code not configured")
        return
    resp = requests.get(f"{pixelcade_url}/weather", params={'location': zip_code, 'ledonly': 'true'}, timeout=5)
    resp.raise_for_status()
    _sleep(mod.get('duration', 13), stop_event)


def _display_clock(cfg, pixelcade_url, stop_event):
    mod = cfg.get('clock', {})
    params = {
        'ledonly': 'true',
        '12h': str(mod.get('twelve_hour', True)).lower(),
        'showSeconds': str(mod.get('show_seconds', True)).lower(),
        'showMilliseconds': str(mod.get('show_milliseconds', False)).lower(),
    }

    color = str(mod.get('color', 'green')).strip()
    if color:
        params['color'] = color

    clock_type = str(mod.get('type', '')).strip()
    if clock_type:
        params['clockType'] = clock_type

    if mod.get('auto_cycle', False):
        params['autoCycle'] = 'true'
        cycle_frequency = str(mod.get('cycle_frequency', '60s')).strip()
        if cycle_frequency:
            params['cycleFrequency'] = cycle_frequency

    extra_params = mod.get('params', {})
    if isinstance(extra_params, dict):
        params.update({k: v for k, v in extra_params.items() if v not in (None, '')})

    resp = requests.get(
        f"{pixelcade_url}/clock",
        params=params,
        timeout=5,
    )
    resp.raise_for_status()
    _sleep(mod.get('duration', 10), stop_event)


def _display_sports(cfg, pixelcade_url, date, stop_event):
    mod = cfg.get('sports', {})
    _update_game_cache(cfg, date)
    seconds_per_game = mod.get('seconds_per_game', 4)
    use_filter = mod.get('use_team_filter', True)
    leagues_cfg = mod.get('leagues', {})

    for league in SUPPORTED_LEAGUES:
        if stop_event.is_set():
            return
        league_cfg = leagues_cfg.get(league, {})
        if not league_cfg.get('enabled', False):
            continue

        games = game_cache.get(league, [])
        teams = [t.strip() for t in league_cfg.get('teams', '').split(',') if t.strip()]

        params = {'ledonly': 'true'}
        if teams and use_filter:
            params['teams'] = ','.join(teams)
            games = [
                g for g in games
                if 'competitions' in g and g['competitions']
                and any(
                    team == comp['team']['abbreviation']
                    for comp in g['competitions'][0].get('competitors', [])
                    for team in teams
                )
            ]

        if not games:
            logging.debug(f"No games for {league} on {date}")
            continue

        resp = requests.get(f"{pixelcade_url}/sports/{league}", params=params, timeout=5)
        resp.raise_for_status()
        if _sleep(max(len(games), 1) * seconds_per_game, stop_event):
            return


def _display_stocks(cfg, pixelcade_url, stop_event):
    mod = cfg.get('stocks', {})
    tickers = mod.get('tickers', '').strip()
    if not tickers:
        logging.warning("Stocks module: no tickers configured")
        return
    resp = requests.get(
        f"{pixelcade_url}/stocks",
        params={'tickers': tickers, 'c': 'blue', 's': '9', 'ledonly': 'true'},
        timeout=5,
    )
    resp.raise_for_status()
    _sleep(mod.get('duration', 10), stop_event)


def _display_pixelcade_widget(module, cfg, pixelcade_url, stop_event):
    widget = PIXELCADE_WIDGET_MODULES[module]
    mod = cfg.get(module, {})
    params = {'ledonly': 'true'}
    if mod.get('nointerrupt', False):
        params['nointerrupt'] = 'true'
    extra_params = mod.get('params', {})
    if isinstance(extra_params, dict):
        params.update({k: v for k, v in extra_params.items() if v not in (None, '')})

    resp = requests.get(
        f"{pixelcade_url}/{widget['endpoint']}",
        params=params,
        timeout=5,
    )
    resp.raise_for_status()
    _sleep(mod.get('duration', widget['default_duration']), stop_event)


def _display_news(cfg, pixelcade_url, stop_event):
    mod = cfg.get('news', {})
    raw = mod.get('rss_feeds', [])
    feeds = [u.strip() for u in (raw.split(',') if isinstance(raw, str) else raw) if u.strip()]
    if not feeds:
        logging.warning("News module: no RSS feeds configured")
        return

    duration_per_feed = mod.get('duration_per_feed', 60)
    max_runtime = mod.get('max_total_runtime', 0)
    elapsed = 0

    for feed_url in feeds:
        if stop_event.is_set():
            return
        if max_runtime and elapsed >= max_runtime:
            break
        try:
            resp = requests.get(
                f"{pixelcade_url}/ticker",
                params={'start': '', 'feed': feed_url, 'c': 'yellow', 's': '8',
                        'newsTickerRefresh': duration_per_feed, 'ledonly': 'true'},
                timeout=5,
            )
            resp.raise_for_status()
        except requests.RequestException as e:
            logging.error(f"News feed error {feed_url}: {e}")
            continue
        if _sleep(duration_per_feed, stop_event):
            return
        elapsed += duration_per_feed


_MODULE_HANDLERS = {
    'weather': _display_weather,
    'clock':   _display_clock,
    'stocks':  _display_stocks,
    'news':    _display_news,
}


def display_module(module, cfg, date, stop_event):
    if stop_event.is_set():
        return

    pixelcade_url = cfg['pixelcade']['url'].rstrip('/')
    timeout = cfg['pixelcade'].get('health_check_timeout', 10)

    with status_lock:
        status['current_module'] = module

    with status_lock:
        was_healthy = status.get('pixelcade_healthy', False)

    try:
        check_pixelcade_health(pixelcade_url, timeout)
        startup_grace_period = cfg.get('pixelcade', {}).get('startup_grace_period', 15)
        with status_lock:
            status['pixelcade_healthy'] = True
        if not was_healthy and startup_grace_period:
            logging.info(f"Waiting {startup_grace_period}s for Pixelcade hardware to settle after reconnect")
            if _sleep(startup_grace_period, stop_event):
                return
            logging.info("Pixelcade recovered and ready")
        elif not was_healthy:
            logging.info("Pixelcade recovered and ready")
    except (requests.RequestException, tenacity.RetryError) as e:
        logging.warning(f"Skipping {module}: Pixelcade offline ({e})")
        with status_lock:
            status['pixelcade_healthy'] = False
        return

    mod_cfg = cfg.get(module, {})
    if not mod_cfg.get('enabled', True):
        return

    try:
        if module == 'sports':
            _display_sports(cfg, pixelcade_url, date, stop_event)
        elif module in _MODULE_HANDLERS:
            _MODULE_HANDLERS[module](cfg, pixelcade_url, stop_event)
        elif module in PIXELCADE_WIDGET_MODULES:
            _display_pixelcade_widget(module, cfg, pixelcade_url, stop_event)
        else:
            logging.warning(f"Unknown module: {module}")
    except requests.RequestException as e:
        logging.error(f"Module {module} request error: {e}")
    except KeyError as e:
        logging.error(f"Module {module} config key missing: {e}")


def main_loop(stop_event):
    logging.info("SportsLooper starting")
    with status_lock:
        status['running'] = True

    cfg = load_config()
    pixelcade_url = cfg['pixelcade']['url'].rstrip('/')
    timeout = cfg['pixelcade'].get('health_check_timeout', 10)
    interval = cfg['pixelcade'].get('health_check_interval', 30)
    startup_grace_period = cfg['pixelcade'].get('startup_grace_period', 15)

    # Wait for Pixelcade to come up
    while not stop_event.is_set():
        try:
            check_pixelcade_health(pixelcade_url, timeout)
            with status_lock:
                status['pixelcade_healthy'] = True
            logging.info("Pixelcade server is up")
            break
        except (requests.RequestException, tenacity.RetryError):
            logging.warning(f"Pixelcade not responding, retrying in {interval}s")
            with status_lock:
                status['pixelcade_healthy'] = False
            stop_event.wait(interval)

    if stop_event.is_set():
        return

    if startup_grace_period:
        logging.info(f"Waiting {startup_grace_period}s for Pixelcade hardware to settle")
        if _sleep(startup_grace_period, stop_event):
            return
        logging.info("Pixelcade startup grace period complete")

    try:
        check_pixelcade_health(pixelcade_url, timeout)
    except (requests.RequestException, tenacity.RetryError) as e:
        logging.warning(f"Startup banner skipped: Pixelcade offline ({e})")
        with status_lock:
            status['pixelcade_healthy'] = False
    else:
        try:
            banner = cfg.get('startup', {}).get('banner', 'SportsLooper')
            resp = requests.get(
                f"{pixelcade_url}/text",
                params={'t': banner, 'l': '10', 'ledonly': 'true'},
                timeout=5,
            )
            resp.raise_for_status()
            _sleep(10, stop_event)
        except Exception as e:
            logging.warning(f"Startup banner failed: {e}")

    current_date = None
    while not stop_event.is_set():
        cfg = load_config()
        date = datetime.now().strftime('%Y%m%d')
        if date != current_date:
            current_date = date
            logging.info(f"Date: {current_date}")

        modules = cfg.get('order', {}).get('sequence', ['weather', 'clock', 'sports', 'stocks', 'news'])
        for module in modules:
            if stop_event.is_set():
                break
            display_module(module, cfg, date, stop_event)

    with status_lock:
        status['running'] = False
        status['current_module'] = None
    logging.info("SportsLooper stopped")
