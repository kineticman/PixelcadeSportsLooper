# --- Auto-generated version block (do not edit by hand) ---
__version__ = "1.1.0"
__version_date__ = "2025-08-16"
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

# Configuration loading from sportslooper.ini
# Look in current working directory first, then script directory
config = configparser.ConfigParser()
ini_file = None

# First try current working directory
current_dir_ini = os.path.join(os.getcwd(), 'sportslooper.ini')
if os.path.exists(current_dir_ini):
    ini_file = current_dir_ini
    print(f"DEBUG: Using INI file from current directory: {ini_file}")
else:
    # Fall back to script directory
    script_dir_ini = os.path.join(SCRIPT_DIR, 'sportslooper.ini')
    if os.path.exists(script_dir_ini):
        ini_file = script_dir_ini
        print(f"DEBUG: Using INI file from script directory: {ini_file}")

if ini_file is None:
    logging.error(f"sportslooper.ini not found in current directory ({os.getcwd()}) or script directory ({SCRIPT_DIR})")
    print(f"Error: sportslooper.ini not found in current directory ({os.getcwd()}) or script directory ({SCRIPT_DIR})")
    exit(1)
else:
    with open(ini_file, 'r') as f:
        content = f.read()
        logging.debug(f"Content of {ini_file}:\n{content}")
        print(f"DEBUG: Content of {ini_file}:\n{content}")
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
    """Check if the Pixelcade server is responsive by sending a test request.
    
    Returns:
        bool: True if the server responds successfully, False after retries fail.
    """
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
    """Fetch game data from ESPN API for a given league and date.
    
    Args:
        league (str): The league identifier (e.g., 'nfl', 'nba').
        date (str): The date in YYYYMMDD format for fetching games.
    
    Returns:
        list: List of game data from the API, or cached data on failure.
    """
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
    """Update the in-memory game cache for enabled leagues.
    
    Args:
        date (str): The date in YYYYMMDD format for fetching games.
    
    Notes:
        - Only fetches data for leagues enabled in sportslooper.ini (set to true).
        - Cache is refreshed every 30 minutes to reduce API calls.
    """
    global game_cache, cache_expiry
    if datetime.now() >= cache_expiry:
        logging.debug("Updating game cache")
        enabled_leagues = [league for league in SUPPORTED_LEAGUES if config.has_option('sports', league) and config.getboolean('sports', league)]
        logging.debug(f"Enabled leagues: {enabled_leagues}")
        game_cache = {league: fetch_espn_games(league, date) for league in enabled_leagues}
        cache_expiry = datetime.now() + timedelta(minutes=30)
        logging.info("Game cache updated.")
        if debug_mode:
            print(f"DEBUG: Cache updated with {len(game_cache)} leagues at {datetime.now()}")

def display_module(module, date, stop_event):
    """Display a module (weather, clock, sports, stocks, news) on the LED marquee if enabled.
    
    Args:
        module (str): The module to display (e.g., 'sports', 'weather').
        date (str): The date in YYYYMMDD format for sports module queries.
        stop_event: threading.Event to check for stop signal.
    
    Notes:
        - Skips modules if the Pixelcade server is down or the module is disabled in sportslooper.ini.
        - Each module has a configurable display duration in the .ini file.
        - Logs to fallback.log when Pixelcade server is offline.
        - Checks stop_event to exit gracefully if stopped.
    """
    logging.debug(f"display_module called with module: '{module}'")
    if debug_mode:
        print(f"DEBUG: display_module() called for: '{module}'")
    
    if stop_event.is_set():
        logging.debug(f"Stop event signaled, skipping module {module}")
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

    # Check if module is enabled (with more detailed logging)
    if not config.has_section(module):
        logging.info(f"Module {module} has no configuration section, skipping.")
        if debug_mode:
            print(f"DEBUG: No [{module}] section found in INI file")
        return
    
    try:
        module_enabled = config.getboolean(module, 'enabled', fallback=True)
        if not module_enabled:
            logging.info(f"Module {module} is disabled, skipping.")
            if debug_mode:
                print(f"DEBUG: Module {module} explicitly disabled (enabled=false)")
            return
    except Exception as e:
        logging.warning(f"Error checking if {module} is enabled, assuming enabled: {e}")
        if debug_mode:
            print(f"DEBUG: Error checking {module} enabled status: {e}, assuming enabled")

    logging.debug(f"Displaying module: {module}")
    try:
        if module == 'weather':
            params = {'location': config['weather']['zip_code'], 'ledonly': 'true'}
            logging.debug(f"Weather params: {params}")
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

        elif module == 'clock':
            params = {'12h': 'true', 'showSeconds': 'true', 'color': 'green', 'ledonly': 'true'}
            logging.debug(f"Clock params: {params}")
            response = requests.get(f"{pixelcade_url}/clock", params=params, timeout=5)
            response.raise_for_status()
            duration = float(config['clock'].get('duration', 10))
            logging.debug(f"Clock display for {duration} seconds")
            if debug_mode:
                print(f"DEBUG: Displaying clock ({duration}s)")
            for _ in range(int(duration)):
                if stop_event.is_set():
                    return
                time.sleep(1)

        elif module == 'sports':
            update_game_cache(date)
            seconds_per_game = float(config['sports'].get('seconds_per_game', 4))
            for league in SUPPORTED_LEAGUES:
                if stop_event.is_set():
                    return
                if not config.has_option('sports', league) or not config.getboolean('sports', league):
                    logging.debug(f"League {league} disabled, skipping")
                    if debug_mode:
                        print(f"DEBUG: Skipping disabled league {league}")
                    continue
                games = game_cache.get(league, [])
                if not games:
                    logging.warning(f"No games for {league} on {date}, check date or API")
                    if debug_mode:
                        print(f"DEBUG: No games for {league} on {date}, check date or API")
                    continue
                teams = config['sports'].get(f"{league}_teams", "").split(',')
                teams = [t.strip() for t in teams if t.strip()]
                params = {'ledonly': 'true'}
                if teams and config['sports'].getboolean('use_team_filter', True):
                    params['teams'] = ','.join(teams)
                    games = [
                        game for game in games
                        if 'competitions' in game and game['competitions'] and 'competitors' in game['competitions'][0]
                        and any(
                            team == comp['team']['abbreviation']
                            for comp in game['competitions'][0].get('competitors', [])
                            for team in teams
                        )
                    ]
                    logging.debug(f"Filtered games for {league} with teams {teams}: {len(games)} games")
                    if debug_mode:
                        print(f"DEBUG: Filtered {league} to {len(games)} games for teams {teams}")
                        print(f"DEBUG: Filtered {league} games: {[game.get('name', 'Unknown') for game in games]}")
                logging.debug(f"Sports params for {league}: {params}")
                response = requests.get(f"{pixelcade_url}/sports/{league}", params=params, timeout=5)
                response.raise_for_status()
                logging.debug(f"Sending Pixelcade request: {response.request.url}")
                display_time = len(games) * seconds_per_game
                display_time = max(display_time, seconds_per_game)
                logging.debug(f"Displaying {league} for {display_time} seconds")
                if debug_mode:
                    print(f"DEBUG: Displaying {league} with {len(games)} games for {display_time}s")
                for _ in range(int(display_time)):
                    if stop_event.is_set():
                        return
                    time.sleep(1)

        elif module == 'stocks':
            params = {
                'tickers': config['stocks']['tickers'],
                'c': 'blue', 's': '9', 'ledonly': 'true'
            }
            logging.debug(f"Stocks params: {params}")
            response = requests.get(f"{pixelcade_url}/stocks", params=params, timeout=5)
            response.raise_for_status()
            duration = float(config['stocks'].get('duration', 10))
            logging.debug(f"Stocks display for {duration} seconds")
            if debug_mode:
                print(f"DEBUG: Displaying stocks {params['tickers']} ({duration}s)")
            for _ in range(int(duration)):
                if stop_event.is_set():
                    return
                time.sleep(1)

        elif module == 'news':
            logging.debug("Processing news module")
            if debug_mode:
                print("DEBUG: Starting news module processing")
            
            feeds = [url.strip() for url in config['news'].get('rss_feeds', '').split(',') if url.strip()]
            if not feeds:
                logging.warning("No RSS feeds configured for news module")
                if debug_mode:
                    print("DEBUG: No RSS feeds found in configuration")
                return
                
            duration_per_feed = config.getint('news', 'duration_per_feed', fallback=60)
            max_total_runtime = config.getint('news', 'max_total_runtime', fallback=0)

            logging.debug(f"News module: {len(feeds)} feeds, {duration_per_feed}s per feed, max runtime: {max_total_runtime}s")
            if debug_mode:
                print(f"DEBUG: News feeds: {feeds}")
                print(f"DEBUG: Duration per feed: {duration_per_feed}s, Max runtime: {max_total_runtime}s")

            total_elapsed = 0
            for feed_url in feeds:
                if max_total_runtime and total_elapsed >= max_total_runtime:
                    logging.debug(f"News module reached max runtime of {max_total_runtime}s")
                    break
                
                params = {
                    'start': '',
                    'feed': feed_url,
                    'c': 'yellow',
                    's': '8',
                    'newsTickerRefresh': duration_per_feed,
                    'ledonly': 'true'
                }
                try:
                    logging.info(f"NEWS FEED -> {feed_url}")
                    if debug_mode:
                        print(f"DEBUG: Sending request to {pixelcade_url}/ticker with feed: {feed_url}")
                    resp = requests.get(f"{pixelcade_url}/ticker", params=params, timeout=5)
                    resp.raise_for_status()
                    if debug_mode:
                        print(f"DEBUG: Displaying news feed {feed_url} for {duration_per_feed}s")
                except requests.RequestException as e:
                    logging.error(f"Failed to display news feed {feed_url}: {e}")
                    if debug_mode:
                        print(f"DEBUG: Error with news feed {feed_url}: {e}")
                    continue
                
                for _ in range(duration_per_feed):
                    if stop_event.is_set():
                        return
                    time.sleep(1)
                total_elapsed += duration_per_feed
                
            logging.debug(f"News module completed, total time: {total_elapsed}s")
            if debug_mode:
                print(f"DEBUG: News module finished, total runtime: {total_elapsed}s")

    except requests.RequestException as e:
        logging.error(f"Error displaying {module}: {e}")
        if debug_mode:
            print(f"DEBUG: Error in {module}: {e}")
    except KeyError as e:
        logging.error(f"Configuration error for {module}: {e}")
        if debug_mode:
            print(f"DEBUG: Config error in {module}: {e}")

def main_loop(stop_event):
    """Main loop for SportsLooper, cycling through enabled modules.
    
    Args:
        stop_event: threading.Event to check for stop signal.
    
    Notes:
        - Checks Pixelcade server health before starting.
        - Displays a startup banner, then loops through modules defined in sportslooper.ini.
        - Uses today's date for sports API queries.
        - Handles stop signals for graceful shutdown.
    """
    logging.info("Starting SportsLooper")
    if debug_mode:
        print("DEBUG: SportsLooper started")

    # Initial health check for Pixelcade server
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

    # Always use today's date for sports queries
    date = datetime.now().strftime('%Y%m%d')

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
            else:
                logging.warning("Skipping startup banner due to Pixelcade server being down")
                if debug_mode:
                    print("DEBUG: Skipping startup banner due to Pixelcade server being down")
                fallback_logger.info("Cannot display startup banner: Pixelcade server offline")
        except (requests.RequestException, tenacity.RetryError):
            logging.warning("Skipping startup banner after retrying Pixelcade server")
            if debug_mode:
                print("DEBUG: Skipping startup banner after retrying Pixelcade server")
            fallback_logger.info("Cannot display startup banner: Pixelcade server offline after retries")
    except requests.RequestException as e:
        logging.error(f"Startup banner error: {e}")
        if debug_mode:
            print(f"DEBUG: Startup banner error: {e}")

    modules = config['order'].get('sequence', 'weather,clock,sports,stocks,news').split(',')
    modules = [m.strip() for m in modules if m.strip()]
    logging.debug(f"Module sequence: {modules}")
    if debug_mode:
        print(f"DEBUG: Module sequence: {modules}")

    if not modules:
        logging.warning("No modules enabled, looping startup banner.")
        if debug_mode:
            print("DEBUG: No modules enabled, looping startup banner")
        while not stop_event.is_set():
            try:
                if check_pixelcade_health():
                    try:
                        response = requests.get(f"{pixelcade_url}/text", params={'t': banner, 'l': '10', 'ledonly': 'true'}, timeout=5)
                        response.raise_for_status()
                        for _ in range(10):
                            if stop_event.is_set():
                                return
                            time.sleep(1)
                    except requests.RequestException as e:
                        logging.error(f"Startup banner loop error: {e}")
                        if debug_mode:
                            print(f"DEBUG: Startup banner loop error: {e}")
                        fallback_logger.info("Cannot display startup banner in loop: Pixelcade server offline")
                        stop_event.wait(health_check_interval)
                else:
                    logging.warning("Skipping startup banner due to Pixelcade server being down")
                    if debug_mode:
                        print("DEBUG: Skipping startup banner due to Pixelcade server being down")
                    fallback_logger.info("Cannot display startup banner in loop: Pixelcade server offline")
                    stop_event.wait(health_check_interval)
            except (requests.RequestException, tenacity.RetryError):
                logging.warning("Skipping startup banner in loop after retrying Pixelcade server")
                if debug_mode:
                    print("DEBUG: Skipping startup banner in loop after retrying Pixelcade server")
                fallback_logger.info("Cannot display startup banner in loop: Pixelcade server offline after retries")
                stop_event.wait(health_check_interval)

    try:
        while not stop_event.is_set():
            for module in modules:
                logging.debug(f"Processing module: {module}")
                if debug_mode:
                    print(f"DEBUG: About to process module: {module}")
                display_module(module, date, stop_event)
                if debug_mode:
                    print(f"DEBUG: Completed processing module: {module}")
    except KeyboardInterrupt:
        logging.info("Shutting down SportsLooper (KeyboardInterrupt)")
        if debug_mode:
            print("DEBUG: Shutting down SportsLooper (KeyboardInterrupt)")
        try:
            if check_pixelcade_health():
                try:
                    requests.get(f"{pixelcade_url}/text", params={'t': 'Shutdown', 'l': '2', 'ledonly': 'true'}, timeout=5)
                except requests.RequestException:
                    pass
        except (requests.RequestException, tenacity.RetryError):
            pass

def signal_handler(sig, frame):
    """Handle SIGINT and SIGTERM signals for graceful shutdown."""
    logging.info("Shutting down SportsLooper (signal received)")
    if debug_mode:
        print("DEBUG: Shutting down SportsLooper (signal received)")
    try:
        if check_pixelcade_health():
            requests.get(f"{pixelcade_url}/text", params={'t': 'Shutdown', 'l': '2', 'ledonly': 'true'}, timeout=5)
    except (requests.RequestException, tenacity.RetryError):
        pass
    sys.exit(0)

def main():
    """Main entry point for Pi version."""
    stop_event = threading.Event()
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    main_loop(stop_event)

if __name__ == "__main__":
    main()