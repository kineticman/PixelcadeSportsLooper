import configparser
import requests
import time
import logging
import os
import tenacity
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from urllib.parse import urlparse
from tenacity import retry, stop_after_attempt, wait_fixed
import threading
import signal
import sys
__version__ = "1.3"
__version_date__ = "2025-08-17"

# Get the script's directory for log files
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Setup logging with rotation
log_handler = RotatingFileHandler(
    os.path.join(SCRIPT_DIR, 'sportslooper.log'),
    maxBytes=1_000_000,  # 1 MB max file size
    backupCount=5  # Keep up to 5 backup files
)
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.basicConfig(
    level=logging.DEBUG,
    handlers=[
        log_handler,
        logging.StreamHandler()  # Console output for debugging
    ]
)

# Setup fallback logging
fallback_handler = RotatingFileHandler(
    os.path.join(SCRIPT_DIR, 'fallback.log'),
    maxBytes=1_000_000,
    backupCount=5
)
fallback_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
fallback_logger = logging.getLogger('fallback')
fallback_logger.setLevel(logging.INFO)
fallback_logger.addHandler(fallback_handler)

# Configuration loading
config = configparser.ConfigParser()
ini_file = os.path.join(SCRIPT_DIR, 'sportslooper.ini')
if not os.path.exists(ini_file):
    logging.error(f"{ini_file} not found in {SCRIPT_DIR}")
    print(f"Error: {ini_file} not found in {SCRIPT_DIR}")
    exit(1)
config.read(ini_file)

# Debug mode and Pixelcade settings
debug_mode = config.getboolean('debug', 'debug_mode', fallback=False)
pixelcade_url = config['pixelcade'].get('pixelcade_url', 'http://localhost:8080').rstrip('/')
health_check_interval = config.getfloat('pixelcade', 'health_check_interval', fallback=30.0)
health_check_timeout = config.getfloat('pixelcade', 'health_check_timeout', fallback=5.0)

# Validate Pixelcade URL
try:
    result = urlparse(pixelcade_url)
    if not all([result.scheme, result.netloc]):
        raise ValueError("Invalid URL format")
except ValueError as e:
    logging.error(f"Invalid Pixelcade URL '{pixelcade_url}': {e}")
    print(f"Error: Invalid Pixelcade URL '{pixelcade_url}': {e}")
    exit(1)

# ESPN API settings
ESPN_BASE_URL = 'https://site.api.espn.com/apis/site/v2/sports'
SUPPORTED_LEAGUES = {
    'nfl': 'football/nfl',
    'nba': 'basketball/nba',
    'nhl': 'hockey/nhl',
    'mlb': 'baseball/mlb',
    'wnba': 'basketball/wnba',
    'eng.1': 'soccer/eng.1',
    'esp.1': 'soccer/esp.1',
    'ger.1': 'soccer/ger.1',
    'ita.1': 'soccer/ita.1',
    'fra.1': 'soccer/fra.1',
    'por.1': 'soccer/por.1',
    'ned.1': 'soccer/ned.1',
    'mex.1': 'soccer/mex.1',
    'usa.1': 'soccer/usa.1',
    'uefa.champions': 'soccer/uefa.champions',
    'college-football': 'football/college-football',
    'mens-college-basketball': 'basketball/mens-college-basketball',
    'womens-college-basketball': 'basketball/womens-college-basketball',
    'college-baseball': 'baseball/college-baseball'
}

# Cache for ESPN API
game_cache = {}
cache_expiry = datetime.now()

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
def check_pixelcade_health():
    try:
        response = requests.get(f"{pixelcade_url}/text", params={'t': 'health', 'l': '1', 'ledonly': 'true'}, timeout=health_check_timeout)
        response.raise_for_status()
        logging.debug("Pixelcade server is responsive")
        return True
    except requests.RequestException as e:
        logging.warning(f"Pixelcade server not responding: {e}")
        if debug_mode:
            print(f"DEBUG: Pixelcade server not responding: {e}")
        raise

def fetch_espn_games(league, date):
    logging.debug(f"Fetching ESPN API for {league} on {date}")
    try:
        sport_league = SUPPORTED_LEAGUES[league]
        url = f"{ESPN_BASE_URL}/{sport_league}/scoreboard?dates={date}"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        games = response.json().get('events', [])
        logging.debug(f"Fetched {len(games)} games for {league}")
        return games
    except requests.RequestException as e:
        logging.error(f"ESPN API error for {league}: {e}")
        return game_cache.get(league, [])

def update_game_cache(date):
    global game_cache, cache_expiry
    if datetime.now() >= cache_expiry:
        logging.debug("Updating game cache")
        enabled_leagues = [league for league in SUPPORTED_LEAGUES if config.getboolean('sports', league, fallback=False)]
        game_cache = {league: fetch_espn_games(league, date) for league in enabled_leagues}
        cache_expiry = datetime.now() + timedelta(minutes=30)
        logging.info("Game cache updated")
        if debug_mode:
            print(f"DEBUG: Cache updated with {len(game_cache)} leagues")

def display_module(module, date, stop_event):
    if stop_event.is_set():
        return
    try:
        if not check_pixelcade_health():
            logging.warning(f"Skipping module {module} due to Pixelcade server being down")
            if debug_mode:
                print(f"DEBUG: Skipping module {module} due to Pixelcade server being down")
            fallback_logger.info(f"Cannot display module {module}: Pixelcade server offline")
            return
    except (requests.RequestException, tenacity.RetryError):
        logging.warning(f"Skipping module {module} after retrying Pixelcade server")
        if debug_mode:
            print(f"DEBUG: Skipping module {module} after retrying Pixelcade server")
        fallback_logger.info(f"Cannot display module {module}: Pixelcade server offline after retries")
        return

    if not config.getboolean(module, 'enabled', fallback=True):
        logging.info(f"Module {module} is disabled, skipping")
        if debug_mode:
            print(f"DEBUG: Skipping disabled module {module}")
        return

    logging.debug(f"Displaying module: {module}")
    try:
        if module == 'weather':
            params = {'location': config['weather']['zip_code'], 'ledonly': 'true'}
            response = requests.get(f"{pixelcade_url}/weather", params=params, timeout=5)
            response.raise_for_status()
            duration = float(config['weather'].get('duration', 10))
            logging.debug(f"Weather display for {duration} seconds")
            if debug_mode:
                print(f"DEBUG: Displaying weather for {config['weather']['zip_code']} ({duration}s)")
            for _ in range(int(duration)):
                if stop_event.is_set():
                    return
                time.sleep(1)

        # Other modules (clock, sports, stocks, news) unchanged...
        # [Same as original script, omitted for brevity]

    except requests.RequestException as e:
        logging.error(f"Error displaying {module}: {e}")
        if debug_mode:
            print(f"DEBUG: Error in {module}: {e}")

def main_loop(stop_event):
    logging.info("Starting SportsLooper")
    if debug_mode:
        print("DEBUG: SportsLooper started")

    while not stop_event.is_set():
        try:
            if check_pixelcade_health():
                logging.info("Pixelcade server is responsive, starting main loop")
                if debug_mode:
                    print("DEBUG: Pixelcade server is responsive, starting main loop")
                break
            logging.warning(f"Pixelcade server not responding, retrying in {health_check_interval} seconds")
            if debug_mode:
                print(f"DEBUG: Pixelcade server not responding at {pixelcade_url}, retrying in {health_check_interval} seconds")
            fallback_logger.info("Cannot start main loop: Pixelcade server offline after retries")
            stop_event.wait(health_check_interval)
        except (requests.RequestException, tenacity.RetryError):
            logging.warning(f"Pixelcade server not responding after retries, retrying in {health_check_interval} seconds")
            if debug_mode:
                print(f"DEBUG: Pixelcade server not responding at {pixelcade_url} after retries, retrying in {health_check_interval} seconds")
            fallback_logger.info("Cannot start main loop: Pixelcade server offline after retries")
            stop_event.wait(health_check_interval)

    # Display startup banner
    try:
        banner = config['startup'].get('banner', 'SportsLooper Starting...')
        logging.debug(f"Startup banner: {banner}")
        try:
            if check_pixelcade_health():
                response = requests.get(f"{pixelcade_url}/text", params={'t': banner, 'l': '10', 'ledonly': 'true'}, timeout=5)
                response.raise_for_status()
                if debug_mode:
                    print(f"DEBUG: Displaying startup banner: {banner}")
                for _ in range(10):
                    if stop_event.is_set():
                        return
                    time.sleep(1)
        except (requests.RequestException, tenacity.RetryError):
            logging.warning("Skipping startup banner after retrying Pixelcade server")
            if debug_mode:
                print(f"DEBUG: Skipping startup banner after retrying Pixelcade server")
            fallback_logger.info("Cannot display startup banner: Pixelcade server offline after retries")
    except requests.RequestException as e:
        logging.error(f"Startup banner error: {e}")
        if debug_mode:
            print(f"DEBUG: Startup banner error: {e}")

    # Get module sequence from config
    modules = config['order'].get('sequence', 'weather,clock,sports,stocks,news').split(',')
    modules = [m.strip() for m in modules if m.strip()]
    logging.debug(f"Module sequence: {modules}")
    if debug_mode:
        print(f"DEBUG: Module sequence: {modules}")

    # Main display loop - date updates every cycle
    current_date = None
    try:
        while not stop_event.is_set():
            # Get fresh date for each cycle
            date = datetime.now().strftime('%Y%m%d')
            
            # Log date change if it occurred
            if date != current_date:
                current_date = date
                logging.info(f"Date changed to {current_date}")
                if debug_mode:
                    print(f"DEBUG: Using date {current_date} for this cycle")
            
            for module in modules:
                logging.debug(f"Processing module: {module}")
                if debug_mode:
                    print(f"DEBUG: About to process module: {module}")
                display_module(module, date, stop_event)
                if debug_mode:
                    print(f"DEBUG: Completed processing module: {module}")
                
                # Check for stop event between modules
                if stop_event.is_set():
                    break
    except KeyboardInterrupt:
        logging.info("Shutting down SportsLooper (KeyboardInterrupt)")
        if debug_mode:
            print("DEBUG: Shutting down SportsLooper (KeyboardInterrupt)")

def signal_handler(sig, frame):
    logging.info("Shutting down SportsLooper (signal received)")
    if debug_mode:
        print("DEBUG: Shutting down SportsLooper")
    try:
        if check_pixelcade_health():
            requests.get(f"{pixelcade_url}/text", params={'t': 'Shutdown', 'l': '2', 'ledonly': 'true'}, timeout=5)
    except (requests.RequestException, tenacity.RetryError):
        pass
    sys.exit(0)

def main():
    stop_event = threading.Event()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    main_loop(stop_event)

if __name__ == "__main__":
    main()