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
import win32serviceutil
import win32service
import win32event
import servicemanager
import sys
import threading

# Get the script's directory for log files
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Setup logging with rotation in the script's directory
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
        logging.StreamHandler()  # Also output logs to console when not running as service
    ]
)

# Setup fallback logging with rotation in the script's directory
fallback_handler = RotatingFileHandler(
    os.path.join(SCRIPT_DIR, 'fallback.log'),
    maxBytes=1_000_000,  # 1 MB max file size
    backupCount=5  # Keep up to 5 backup files
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

# Debug mode and Pixelcade settings from INI
debug_mode = config.getboolean('debug', 'debug_mode', fallback=False)  # Enable debug logging to console
pixelcade_url = config['pixelcade'].get('pixelcade_url', 'http://localhost:8080').rstrip('/')  # Base URL for Pixelcade server
health_check_interval = config.getfloat('pixelcade', 'health_check_interval', fallback=10.0)  # Seconds between health checks
health_check_timeout = config.getfloat('pixelcade', 'health_check_timeout', fallback=5.0)  # Timeout for health check requests

# Validate Pixelcade URL format
try:
    result = urlparse(pixelcade_url)
    if not all([result.scheme, result.netloc]):
        raise ValueError("Invalid URL format")
except ValueError as e:
    logging.error(f"Invalid Pixelcade URL '{pixelcade_url}': {e}")
    print(f"Error: Invalid Pixelcade URL '{pixelcade_url}': {e}")
    exit(1)

# ESPN API base URL and supported leagues
ESPN_BASE_URL = 'https://site.api.espn.com/apis/site/v2/sports'  # Base URL for ESPN API scoreboards
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

# Cache for ESPN API (in-memory, refreshed every 30 minutes)
game_cache = {}  # Stores game data for enabled leagues
cache_expiry = datetime.now()  # Timestamp for when cache should be refreshed

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))  # Retry 3 times with 2-second delay
def check_pixelcade_health():
    """Check if the Pixelcade server is responsive by sending a test request.
    
    Returns:
        bool: True if the server responds successfully, False after retries fail.
    """
    try:
        response = requests.get(f"{pixelcade_url}/text", params={'t': 'health', 'l': '1', 'ledonly': 'true'}, timeout=health_check_interval)
        response.raise_for_status()
        logging.debug("Pixelcade server is responsive")
        return True
    except requests.RequestException as e:
        logging.warning(f"Pixelcade server not responding: {e}")
        if debug_mode:
            print(f"DEBUG: Pixelcade server not responding: {e}")
        raise  # Re-raise for retry logic

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
        return game_cache.get(league, [])  # Fallback to cache if API call fails

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

def is_event_signaled(event):
    """Check if an event is signaled, handling both threading.Event and win32event.
    
    Args:
        event: Either a threading.Event or a win32event PyHANDLE.
    
    Returns:
        bool: True if the event is signaled, False otherwise.
    """
    if isinstance(event, threading.Event):
        return event.is_set()
    else:  # Assume win32event PyHANDLE
        return win32event.WaitForSingleObject(event, 0) == win32event.WAIT_OBJECT_0

def display_module(module, date, stop_event):
    """Display a module (weather, clock, sports, stocks, news) on the LED marquee if enabled.
    
    Args:
        module (str): The module to display (e.g., 'sports', 'weather').
        date (str): The date in YYYYMMDD format for sports module queries.
        stop_event: Either threading.Event or win32event PyHANDLE to check for service stop signal.
    
    Notes:
        - Skips modules if the Pixelcade server is down or the module is disabled in sportslooper.ini.
        - Each module has a configurable display duration in the .ini file.
        - Logs to fallback.log when Pixelcade server is offline.
        - Checks stop_event to exit gracefully if service is stopped.
    """
    if is_event_signaled(stop_event):
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
            params = {'location': config['weather']['zip_code'], 'ledonly': 'true'}  # Use zip code from .ini
            logging.debug(f"Weather params: {params}")
            response = requests.get(f"{pixelcade_url}/weather", params=params, timeout=5)
            response.raise_for_status()
            duration = float(config['weather'].get('duration', 10))  # Display duration in seconds
            logging.debug(f"Weather display for {duration} seconds")
            if debug_mode:
                print(f"DEBUG: Displaying weather for {config['weather']['zip_code']} ({duration}s)")
            for _ in range(int(duration)):
                if is_event_signaled(stop_event):
                    return
                time.sleep(1)
        
        elif module == 'clock':
            params = {'12h': 'true', 'showSeconds': 'true', 'color': 'green', 'ledonly': 'true'}  # Hardcoded clock settings
            logging.debug(f"Clock params: {params}")
            response = requests.get(f"{pixelcade_url}/clock", params=params, timeout=5)
            response.raise_for_status()
            duration = float(config['clock'].get('duration', 10))  # Display duration in seconds
            logging.debug(f"Clock display for {duration} seconds")
            if debug_mode:
                print(f"DEBUG: Displaying clock ({duration}s)")
            for _ in range(int(duration)):
                if is_event_signaled(stop_event):
                    return
                time.sleep(1)
        
        elif module == 'sports':
            update_game_cache(date)  # Refresh game cache if expired
            seconds_per_game = float(config['sports'].get('seconds_per_game', 4))  # Seconds to display each game
            for league in SUPPORTED_LEAGUES:
                if is_event_signaled(stop_event):
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
                teams = config['sports'].get(f"{league}_teams", "").split(',')  # Team filter from .ini (e.g., 'NYY,BOS')
                teams = [t.strip() for t in teams if t.strip()]
                params = {'ledonly': 'true'}
                if teams and config['sports'].getboolean('use_team_filter', True):
                    params['teams'] = ','.join(teams)  # Filter games by specified teams
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
                display_time = max(display_time, seconds_per_game)  # Ensure at least one game's duration
                logging.debug(f"Displaying {league} for {display_time} seconds")
                if debug_mode:
                    print(f"DEBUG: Displaying {league} with {len(games)} games for {display_time}s")
                for _ in range(int(display_time)):
                    if is_event_signaled(stop_event):
                        return
                    time.sleep(1)
        
        elif module == 'stocks':
            params = {
                'tickers': config['stocks']['tickers'],  # Stock tickers from .ini (e.g., 'AAPL,GOOGL')
                'c': 'blue', 's': '9', 'ledonly': 'true'  # Hardcoded display settings
            }
            logging.debug(f"Stocks params: {params}")
            response = requests.get(f"{pixelcade_url}/stocks", params=params, timeout=5)
            response.raise_for_status()
            duration = float(config['stocks'].get('duration', 10))  # Display duration in seconds
            logging.debug(f"Stocks display for {duration} seconds")
            if debug_mode:
                print(f"DEBUG: Displaying stocks {params['tickers']} ({duration}s)")
            for _ in range(int(duration)):
                if is_event_signaled(stop_event):
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
                    if is_event_signaled(stop_event):
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
        stop_event: Either threading.Event or win32event PyHANDLE to check for service stop signal.
    
    Notes:
        - Checks Pixelcade server health before starting.
        - Displays a startup banner, then loops through modules defined in sportslooper.ini.
        - Uses fresh date for each cycle to handle day changes properly.
        - Handles service stop signals and keyboard interrupts for graceful shutdown.
    """
    logging.info("Starting SportsLooper")
    if debug_mode:
        print("DEBUG: SportsLooper started")
    
    # Initial health check for Pixelcade server
    while not is_event_signaled(stop_event):
        try:
            if check_pixelcade_health():
                logging.info("Pixelcade server is responsive, starting main loop")
                if debug_mode:
                    print("DEBUG: Pixelcade server is responsive, starting main loop")
                break
            logging.warning("Pixelcade server not responding, retrying in {} seconds".format(health_check_interval))
            if debug_mode:
                print(f"DEBUG: Pixelcade server not responding at {pixelcade_url}, retrying in {health_check_interval} seconds")
            fallback_logger.info("Cannot start main loop: Pixelcade server offline after retries")
            if isinstance(stop_event, threading.Event):
                stop_event.wait(health_check_interval)
            else:
                win32event.WaitForSingleObject(stop_event, int(health_check_interval * 1000))
        except (requests.RequestException, tenacity.RetryError):
            logging.warning("Pixelcade server not responding after retries, retrying in {} seconds".format(health_check_interval))
            if debug_mode:
                print(f"DEBUG: Pixelcade server not responding at {pixelcade_url} after retries, retrying in {health_check_interval} seconds")
            fallback_logger.info("Cannot start main loop: Pixelcade server offline after retries")
            if isinstance(stop_event, threading.Event):
                stop_event.wait(health_check_interval)
            else:
                win32event.WaitForSingleObject(stop_event, int(health_check_interval * 1000))
    
    try:
        banner = config['startup'].get('banner', 'SportsLooper Starting...')  # Startup message from .ini
        logging.debug(f"Startup banner: {banner}")
        try:
            if check_pixelcade_health():
                response = requests.get(f"{pixelcade_url}/text", params={'t': banner, 'l': '10', 'ledonly': 'true'}, timeout=5)
                response.raise_for_status()
                if debug_mode:
                    print(f"DEBUG: Displaying startup banner: {banner}")
                for _ in range(10):
                    if is_event_signaled(stop_event):
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
                print(f"DEBUG: Skipping startup banner after retrying Pixelcade server")
            fallback_logger.info("Cannot display startup banner: Pixelcade server offline after retries")
    except requests.RequestException as e:
        logging.error(f"Startup banner error: {e}")
        if debug_mode:
            print(f"DEBUG: Startup banner error: {e}")
    
    modules = config['order'].get('sequence', 'weather,clock,sports,stocks,news').split(',')  # Module order from .ini
    modules = [m.strip() for m in modules if m.strip()]
    logging.debug(f"Module sequence: {modules}")
    if debug_mode:
        print(f"DEBUG: Module sequence: {modules}")
    
    if not modules:
        logging.warning("No modules enabled, looping startup banner.")
        if debug_mode:
            print("DEBUG: No modules enabled, looping startup banner")
        while not is_event_signaled(stop_event):
            try:
                if check_pixelcade_health():
                    try:
                        response = requests.get(f"{pixelcade_url}/text", params={'t': banner, 'l': '10', 'ledonly': 'true'}, timeout=5)
                        response.raise_for_status()
                        for _ in range(10):
                            if is_event_signaled(stop_event):
                                return
                            time.sleep(1)
                    except requests.RequestException as e:
                        logging.error(f"Startup banner loop error: {e}")
                        if debug_mode:
                            print(f"DEBUG: Startup banner loop error: {e}")
                        fallback_logger.info("Cannot display startup banner in loop: Pixelcade server offline")
                        if isinstance(stop_event, threading.Event):
                            stop_event.wait(health_check_interval)
                        else:
                            win32event.WaitForSingleObject(stop_event, int(health_check_interval * 1000))
                else:
                    logging.warning("Skipping startup banner due to Pixelcade server being down")
                    if debug_mode:
                        print("DEBUG: Skipping startup banner due to Pixelcade server being down")
                    fallback_logger.info("Cannot display startup banner in loop: Pixelcade server offline")
                    if isinstance(stop_event, threading.Event):
                        stop_event.wait(health_check_interval)
                    else:
                        win32event.WaitForSingleObject(stop_event, int(health_check_interval * 1000))
            except (requests.RequestException, tenacity.RetryError):
                logging.warning("Skipping startup banner in loop after retrying Pixelcade server")
                if debug_mode:
                    print(f"DEBUG: Skipping startup banner in loop after retrying Pixelcade server")
                fallback_logger.info("Cannot display startup banner in loop: Pixelcade server offline after retries")
                if isinstance(stop_event, threading.Event):
                    stop_event.wait(health_check_interval)
                else:
                    win32event.WaitForSingleObject(stop_event, int(health_check_interval * 1000))
    
    # Main display loop - date updates every cycle
    current_date = None
    try:
        while not is_event_signaled(stop_event):
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
                if is_event_signaled(stop_event):
                    break
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

class SportsLooperService(win32serviceutil.ServiceFramework):
    _svc_name_ = "SportsLooper"
    _svc_display_name_ = "SportsLooper Service"
    _svc_description_ = "Runs SportsLooper to display sports, weather, and other info on Pixelcade LED marquee"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = False

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.stop_event)
        self.running = False
        self.ReportServiceStatus(win32service.SERVICE_STOPPED)

    def SvcDoRun(self):
        try:
            servicemanager.LogMsg(
                servicemanager.EVENTLOG_INFORMATION_TYPE,
                servicemanager.PYS_SERVICE_STARTED,
                (self._svc_name_, '')
            )
            self.running = True
            main_loop(self.stop_event)
        except Exception as e:
            logging.error(f"Service failed: {e}")
            with open(os.path.join(SCRIPT_DIR, 'service_error.log'), 'a') as f:
                f.write(f"{datetime.now()}: Service failed: {e}\n")
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STOPPED,
            (self._svc_name_, '')
        )

def main():
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(SportsLooperService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(SportsLooperService)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Handle service commands (install, start, stop, remove)
        win32serviceutil.HandleCommandLine(SportsLooperService)
    else:
        # Run as a regular script for testing
        stop_event = threading.Event()
        main_loop(stop_event)