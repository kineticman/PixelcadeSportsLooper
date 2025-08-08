import servicemanager
import win32serviceutil
import win32service
import win32event
import win32api
import logging
import logging.handlers
import time
import threading
import sys
import os
import socket
from datetime import datetime, timezone
import requests
from urllib.parse import quote_plus
from typing import List, Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from urllib3.exceptions import NameResolutionError
import dns.resolver
import configparser

# Version information
__version__ = "1.0.7"
__version_date__ = "2025-08-08"
__version_date__ = "2025-08-08"
# Early logging setup to capture all errors
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)

# Check for required dependencies
try:
    import requests
    import dns.resolver
    import tenacity
    import win32serviceutil
    import configparser
except ImportError as e:
    logging.error(f"Missing required Python library: {e}", extra={'force': True})
    sys.exit(1)

# Global configuration variables (will be loaded from .ini file)
CONFIG = {}

def load_configuration():
    """Load configuration from .ini file with fallback to defaults."""
    global CONFIG
    
    config = configparser.ConfigParser()
    
    # Try multiple locations for the config file
    script_dir = os.path.dirname(os.path.abspath(__file__))
    possible_locations = [
        os.path.join(script_dir, 'pixelcade_sports.ini'),
        r'C:\pixelcade\SportsLooper\pixelcade_sports.ini',
        r'C:\pixelcade\scripts\pixelcade_sports.ini',
        r'C:\pixelcade\pixelcade_sports.ini',
    ]
    
    config_file = None
    for location in possible_locations:
        if os.path.exists(location):
            config_file = location
            break
    
    if config_file is None:
        config_file = r'C:\pixelcade\SportsLooper\pixelcade_sports.ini'
    
    # Default configuration
    defaults = {
        'display': {
            'display_time_min': '15',
            'display_time_max': '80',
            'seconds_per_game': '6',
            'refresh_interval': '600'
        },
        'timing': {
            'cooldown_default': '120',
            'cooldown_ncaam_400_error': '120',
            'cooldown_inactive': '120',
            'startup_delay': '60',
            'error_retry_delay': '30'
        },
        'network': {
            'api_timeout': '10',
            'retry_attempts': '3',
            'retry_min_wait': '2',
            'retry_max_wait': '10',
            'connectivity_max_attempts': '10',
            'connectivity_retry_delay': '15',
            'dns_servers': '8.8.8.8,8.8.4.4',
            'connectivity_test_host': '8.8.8.8',
            'connectivity_test_port': '53'
        },
        'circuit_breaker': {
            'failure_threshold': '5',
            'timeout': '300'
        },
        'logging': {
            'log_directory': r'C:\pixelcade\SportsLooper\logs',
            'log_filename': 'scores_service.log',
            'max_log_size': '1048576',
            'backup_count': '2'
        },
        'service': {
            'worker_thread_timeout': '30.0',
            'loading_message': "Brad's Bar - now loading"
        },
        'environment': {
            'pixelcade_base_url': 'http://localhost:8080',
            'zip_code': '43017',
            'weather_display_duration': '20',
            'loading_display_duration': '30'
        },
        'league_toggles': {
            'mlb': 'true',
            'nba': 'true',
            'nfl': 'true',
            'nhl': 'true',
            'wnba': 'true',
            'mls': 'true',
            'epl': 'true',
            'laliga': 'true',
            'bundesliga': 'true',
            'seriea': 'true',
            'ligue1': 'true',
            'ucl': 'true',
            'ncaaf': 'true',
            'ncaam': 'true',
            'ncaaw': 'true',
            'ncaabb': 'true'
        },
        'espn_endpoints': {
            'mlb': 'baseball/mlb',
            'nba': 'basketball/nba',
            'nfl': 'football/nfl',
            'nhl': 'hockey/nhl',
            'wnba': 'basketball/wnba',
            'mls': 'soccer/usa.1',
            'epl': 'soccer/eng.1',
            'laliga': 'soccer/esp.1',
            'bundesliga': 'soccer/ger.1',
            'seriea': 'soccer/ita.1',
            'ligue1': 'soccer/fra.1',
            'ucl': 'soccer/uefa.champions',
            'ncaaf': 'football/college-football',
            'ncaam': 'basketball/mens-college-basketball',
            'ncaaw': 'basketball/womens-college-basketball',
            'ncaabb': 'baseball/college-baseball'
        },
        'pixelcade_leagues': {
            'mlb': 'mlb',
            'nba': 'nba',
            'nfl': 'nfl',
            'nhl': 'nhl',
            'wnba': 'wnba',
            'mls': 'usa.1',
            'epl': 'eng.1',
            'laliga': 'esp.1',
            'bundesliga': 'ger.1',
            'seriea': 'ita.1',
            'ligue1': 'fra.1',
            'ucl': 'uefa.champions',
            'ncaaf': 'college-football',
            'ncaam': 'mens-college-basketball',
            'ncaaw': 'womens-college-basketball',
            'ncaabb': 'college-baseball'
        }
    }
    
    # Load defaults first
    for section, options in defaults.items():
        config.add_section(section)
        for key, value in options.items():
            config.set(section, key, value)
    
    # Try to read the configuration file
    if os.path.exists(config_file):
        try:
            config.read(config_file)
            logging.info(f"Configuration loaded from {config_file}", extra={'force': True})
        except Exception as e:
            logging.warning(f"Error reading config file {config_file}: {e}. Using defaults.", extra={'force': True})
    else:
        logging.info(f"Config file {config_file} not found. Using defaults.", extra={'force': True})
        try:
            create_sample_config_file(config_file, config)
        except Exception as e:
            logging.warning(f"Could not create sample config file: {e}", extra={'force': True})
    
    # Convert to our CONFIG dictionary with proper type conversion
    CONFIG = {}
    
    # Display settings
    CONFIG['DISPLAY_TIME_MIN'] = config.getint('display', 'display_time_min')
    CONFIG['DISPLAY_TIME_MAX'] = config.getint('display', 'display_time_max')
    CONFIG['SECONDS_PER_GAME'] = config.getint('display', 'seconds_per_game')
    # New in v1.0.7: optional cap from INI
    CONFIG['MAX_TOTAL_DISPLAY_TIME'] = config.getint('display', 'max_total_display_time', fallback=120)
    CONFIG['REFRESH_INTERVAL'] = config.getint('display', 'refresh_interval')
    
    # Timing settings
    CONFIG['COOLDOWN_DEFAULT'] = config.getint('timing', 'cooldown_default')
    CONFIG['COOLDOWN_NCAAM_400_ERROR'] = config.getint('timing', 'cooldown_ncaam_400_error')
    CONFIG['COOLDOWN_INACTIVE'] = config.getint('timing', 'cooldown_inactive')
    CONFIG['STARTUP_DELAY'] = config.getint('timing', 'startup_delay')
    CONFIG['ERROR_RETRY_DELAY'] = config.getint('timing', 'error_retry_delay')
    
    # Network settings
    CONFIG['API_TIMEOUT'] = config.getint('network', 'api_timeout')
    CONFIG['RETRY_ATTEMPTS'] = config.getint('network', 'retry_attempts')
    CONFIG['RETRY_MIN_WAIT'] = config.getint('network', 'retry_min_wait')
    CONFIG['RETRY_MAX_WAIT'] = config.getint('network', 'retry_max_wait')
    CONFIG['CONNECTIVITY_MAX_ATTEMPTS'] = config.getint('network', 'connectivity_max_attempts')
    CONFIG['CONNECTIVITY_RETRY_DELAY'] = config.getint('network', 'connectivity_retry_delay')
    CONFIG['DNS_SERVERS'] = [s.strip() for s in config.get('network', 'dns_servers').split(',')]
    CONFIG['CONNECTIVITY_TEST_HOST'] = config.get('network', 'connectivity_test_host')
    CONFIG['CONNECTIVITY_TEST_PORT'] = config.getint('network', 'connectivity_test_port')
    
    # Circuit breaker settings
    CONFIG['CIRCUIT_BREAKER_THRESHOLD'] = config.getint('circuit_breaker', 'failure_threshold')
    CONFIG['CIRCUIT_BREAKER_TIMEOUT'] = config.getint('circuit_breaker', 'timeout')
    
    # Logging settings
    CONFIG['LOG_DIRECTORY'] = config.get('logging', 'log_directory')
    CONFIG['LOG_FILENAME'] = config.get('logging', 'log_filename')
    CONFIG['MAX_LOG_SIZE'] = config.getint('logging', 'max_log_size')
    CONFIG['BACKUP_COUNT'] = config.getint('logging', 'backup_count')
    
    # Service settings
    CONFIG['WORKER_THREAD_TIMEOUT'] = config.getfloat('service', 'worker_thread_timeout')
    CONFIG['LOADING_MESSAGE'] = config.get('service', 'loading_message')
    
    # Environment settings
    CONFIG['PIXELCADE_BASE_URL'] = os.getenv('PIXELCADE_BASE_URL', config.get('environment', 'pixelcade_base_url')).strip()
    CONFIG['ZIP_CODE'] = os.getenv('ZIP_CODE', config.get('environment', 'zip_code')).strip()
    
    try:
        CONFIG['WEATHER_DISPLAY_DURATION'] = int(os.getenv('WEATHER_DISPLAY_DURATION', config.get('environment', 'weather_display_duration')))
        if CONFIG['WEATHER_DISPLAY_DURATION'] <= 0:
            raise ValueError("Must be positive")
    except (ValueError, TypeError):
        CONFIG['WEATHER_DISPLAY_DURATION'] = 20
        logging.warning("Invalid WEATHER_DISPLAY_DURATION, using default: 20", extra={'force': True})
    
    try:
        CONFIG['LOADING_DISPLAY_DURATION'] = int(os.getenv('LOADING_DISPLAY_DURATION', config.get('environment', 'loading_display_duration')))
        if CONFIG['LOADING_DISPLAY_DURATION'] <= 0:
            raise ValueError("Must be positive")
    except (ValueError, TypeError):
        CONFIG['LOADING_DISPLAY_DURATION'] = 30
        logging.warning("Invalid LOADING_DISPLAY_DURATION, using default: 30", extra={'force': True})
    
    # League toggles
    CONFIG['LEAGUE_TOGGLES'] = {}
    for league in config.options('league_toggles'):
        CONFIG['LEAGUE_TOGGLES'][league] = config.getboolean('league_toggles', league)
    
    # ESPN endpoints
    CONFIG['ESPN_API_ENDPOINTS'] = dict(config.items('espn_endpoints'))
    
    # Pixelcade league mappings
    CONFIG['PIXELCADE_LEAGUE_MAP'] = dict(config.items('pixelcade_leagues'))
    
    # Validate required settings
    if not CONFIG['PIXELCADE_BASE_URL']:
        CONFIG['PIXELCADE_BASE_URL'] = "http://localhost:8080"
        logging.warning("Empty PIXELCADE_BASE_URL, using default: http://localhost:8080", extra={'force': True})
    
    if not CONFIG['ZIP_CODE']:
        CONFIG['ZIP_CODE'] = "43017"
        logging.warning("Empty ZIP_CODE, using default: 43017", extra={'force': True})
    
    # Validate league configurations
    enabled_leagues = set(CONFIG['LEAGUE_TOGGLES'].keys())
    espn_leagues = set(CONFIG['ESPN_API_ENDPOINTS'].keys())
    pixelcade_leagues = set(CONFIG['PIXELCADE_LEAGUE_MAP'].keys())
    if enabled_leagues != espn_leagues or enabled_leagues != pixelcade_leagues:
        logging.warning(
            f"League configuration mismatch: toggles={enabled_leagues}, espn={espn_leagues}, pixelcade={pixelcade_leagues}. Using intersection.",
            extra={'force': True}
        )
        common_leagues = enabled_leagues & espn_leagues & pixelcade_leagues
        CONFIG['LEAGUE_TOGGLES'] = {k: v for k, v in CONFIG['LEAGUE_TOGGLES'].items() if k in common_leagues}
        CONFIG['ESPN_API_ENDPOINTS'] = {k: v for k, v in CONFIG['ESPN_API_ENDPOINTS'].items() if k in common_leagues}
        CONFIG['PIXELCADE_LEAGUE_MAP'] = {k: v for k, v in CONFIG['PIXELCADE_LEAGUE_MAP'].items() if k in common_leagues}
    

def create_sample_config_file(config_file: str, config: configparser.ConfigParser):
    """Create a sample configuration file with current defaults."""
    try:
        config_dir = os.path.dirname(config_file)
        os.makedirs(config_dir, exist_ok=True)
        
        with open(config_file, 'w') as f:
            f.write("""# Pixelcade Sports Service Configuration File
# Default location: C:\\pixelcade\\SportsLooper\\pixelcade_sports.ini
# Edit values below to customize service behavior
# Remove the semicolon (;) at the beginning of lines to activate settings

""")
            config.write(f)
        logging.info(f"Sample configuration file created at {config_file}", extra={'force': True})
    except Exception as e:
        logging.warning(f"Failed to create sample config file: {e}", extra={'force': True})

# Load configuration on startup
load_configuration()

# Track NameResolutionError to avoid repetitive logging
name_resolution_logged = set()

# Circuit breaker for API calls
api_failure_counts = {}

def now_utc() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(timezone.utc)

def is_circuit_breaker_open(endpoint: str) -> bool:
    """Check if circuit breaker is open for an endpoint."""
    if endpoint not in api_failure_counts:
        return False
    
    failure_count, last_failure_time = api_failure_counts[endpoint]
    
    if time.time() - last_failure_time > CONFIG['CIRCUIT_BREAKER_TIMEOUT']:
        del api_failure_counts[endpoint]
        return False
    
    return failure_count >= CONFIG['CIRCUIT_BREAKER_THRESHOLD']

def record_api_failure(endpoint: str):
    """Record an API failure for circuit breaker."""
    if endpoint not in api_failure_counts:
        api_failure_counts[endpoint] = [0, time.time()]
    
    api_failure_counts[endpoint][0] += 1
    api_failure_counts[endpoint][1] = time.time()

def record_api_success(endpoint: str):
    """Record an API success, resetting circuit breaker."""
    if endpoint in api_failure_counts:
        del api_failure_counts[endpoint]

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.exceptions.ConnectionError, requests.exceptions.Timeout, NameResolutionError)),
    reraise=True
)
def fetch_schedule(league: str) -> Optional[List[dict]]:
    """Fetch the schedule for a given sports league from the ESPN API."""
    global name_resolution_logged
    
    endpoint = f"espn_api_{league}"
    if is_circuit_breaker_open(endpoint):
        logging.warning(f"Circuit breaker open for {league}, skipping API call", extra={'force': True})
        return None
    
    try:
        current_date = datetime.now(timezone.utc).strftime("%Y%m%d")
        url = f"https://site.api.espn.com/apis/site/v2/sports/{CONFIG['ESPN_API_ENDPOINTS'][league]}/scoreboard?date={current_date}"
        logging.info(f"Fetching schedule for {league} from {url}", extra={'force': True})
        resp = requests.get(url, timeout=CONFIG['API_TIMEOUT'])
        resp.raise_for_status()
        
        name_resolution_logged.discard(league)
        record_api_success(endpoint)
        return resp.json().get("events", [])
        
    except dns.resolver.NXDOMAIN:
        if league not in name_resolution_logged:
            logging.error(f"DNS resolution failed for site.api.espn.com: Domain does not exist", extra={'force': True})
            name_resolution_logged.add(league)
        record_api_failure(endpoint)
        return None
    except dns.resolver.NoAnswer:
        if league not in name_resolution_logged:
            logging.error(f"DNS resolution failed for site.api.espn.com: No answer received", extra={'force': True})
            name_resolution_logged.add(league)
        record_api_failure(endpoint)
        return None
    except dns.resolver.Timeout:
        if league not in name_resolution_logged:
            logging.error(f"DNS resolution timeout for site.api.espn.com", extra={'force': True})
            name_resolution_logged.add(league)
        record_api_failure(endpoint)
        return None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400 and league == "ncaam":
            logging.warning(f"HTTP 400 error for {league}, likely off-season or invalid parameters: {e}", extra={'force': True})
            return None
        logging.error(f"HTTP error fetching {league} schedule: {e}", extra={'force': True})
        record_api_failure(endpoint)
        return None
    except (requests.exceptions.ConnectionError, NameResolutionError) as e:
        if league not in name_resolution_logged:
            logging.error(f"Connection error fetching {league} schedule: {e}", extra={'force': True})
            name_resolution_logged.add(league)
        record_api_failure(endpoint)
        raise
    except requests.exceptions.Timeout as e:
        logging.error(f"Timeout fetching {league} schedule: {e}", extra={'force': True})
        record_api_failure(endpoint)
        raise
    except requests.exceptions.RequestException as e:
        logging.error(f"Request error fetching {league} schedule: {e}", extra={'force': True})
        record_api_failure(endpoint)
        return None
    except ValueError as e:
        logging.error(f"JSON parsing error for {league} schedule: {e}", extra={'force': True})
        record_api_failure(endpoint)
        return None

def is_event_within_24_hours(event: dict) -> bool:
    now = now_utc()
    try:
        start_str = event.get("date") or event.get("startDate") or event.get("scheduled")
        if not start_str:
            return False
        if start_str.endswith("Z"):
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        elif "+" in start_str or start_str.endswith(("00", "30")):
            start = datetime.fromisoformat(start_str)
        else:
            start = datetime.fromisoformat(start_str).replace(tzinfo=timezone.utc)
    except Exception:
        return False
    time_diff = (start - now).total_seconds()
    if abs(time_diff) <= 86400:
        return True
    status_type = event.get("status", {}).get("type", {}).get("name", "").lower()
    if "final" in status_type:
        elapsed = (now - start).total_seconds()
        return 0 <= elapsed <= 86400
    return False

def has_relevant_games(events: Optional[List[dict]]) -> bool:
    """Check if there are relevant games (within 24 hours or recently finished) in the events."""
    if not events:
        return False
    now = now_utc()
    for event in events:
        try:
            start_str = event.get("date") or event.get("startDate") or event.get("scheduled")
            if not start_str:
                continue
            
            if start_str.endswith('Z'):
                start = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            elif '+' in start_str or start_str.endswith(('00', '30')):
                start = datetime.fromisoformat(start_str)
            else:
                start = datetime.fromisoformat(start_str).replace(tzinfo=timezone.utc)
                
            logging.debug(f"Event for {event.get('league', 'unknown')}: start={start_str}, status={event.get('status', {}).get('type', {}).get('name', '')}", extra={'force': True})
        except Exception as e:
            logging.error(f"Error parsing event date: {e}", extra={'force': True})
            continue
            
        status_type = event.get("status", {}).get("type", {}).get("name", "").lower()
        time_diff = (start - now).total_seconds()

        if abs(time_diff) <= 24 * 3600:
            return True

        if "final" in status_type:
            elapsed = (now - start).total_seconds()
            if 0 <= elapsed <= 24 * 3600:
                return True
    return False

def calculate_display_time(num_games: int) -> int:
    """Calculate the display time for a league based on the number of games."""
    if num_games < 0:
        logging.warning(f"Negative number of games ({num_games}), using minimum display time", extra={'force': True})
        return CONFIG['DISPLAY_TIME_MIN']
    return max(CONFIG['DISPLAY_TIME_MIN'], min(num_games * CONFIG['SECONDS_PER_GAME'], CONFIG['MAX_TOTAL_DISPLAY_TIME']))

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.exceptions.ConnectionError, requests.exceptions.Timeout)),
    reraise=True
)
def call_pixelcade_sports(league: str, display_seconds: int) -> None:
    """Call the Pixelcade API to display sports data for a league."""
    endpoint = "pixelcade_sports"
    if is_circuit_breaker_open(endpoint):
        logging.warning(f"Circuit breaker open for Pixelcade sports API, skipping call", extra={'force': True})
        return
    
    pixelcade_league = CONFIG['PIXELCADE_LEAGUE_MAP'].get(league, league)
    url = f"{CONFIG['PIXELCADE_BASE_URL']}/sports/{pixelcade_league}?teams="
    try:
        logging.info(f"Calling Pixelcade sports API for {pixelcade_league}, will display for {display_seconds} seconds", extra={'force': True})
        resp = requests.get(url, timeout=CONFIG['API_TIMEOUT'])
        resp.raise_for_status()
        record_api_success(endpoint)
    except Exception as e:
        logging.error(f"Pixelcade sports widget call failed for {pixelcade_league}: {e}", extra={'force': True})
        record_api_failure(endpoint)
        raise

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.exceptions.ConnectionError, requests.exceptions.Timeout)),
    reraise=True
)
def call_pixelcade_weather() -> None:
    """Call the Pixelcade API to display weather data for the configured location."""
    endpoint = "pixelcade_weather"
    if is_circuit_breaker_open(endpoint):
        logging.warning(f"Circuit breaker open for Pixelcade weather API, skipping call", extra={'force': True})
        return
    
    location_param = quote_plus(CONFIG['ZIP_CODE'])
    url = f"{CONFIG['PIXELCADE_BASE_URL']}/weather?location={location_param}"
    try:
        logging.info(f"Calling Pixelcade weather API for location {CONFIG['ZIP_CODE']}, will display for {CONFIG['WEATHER_DISPLAY_DURATION']} seconds", extra={'force': True})
        resp = requests.get(url, timeout=CONFIG['API_TIMEOUT'])
        resp.raise_for_status()
        record_api_success(endpoint)
    except Exception as e:
        logging.error(f"Pixelcade weather widget call failed: {e}", extra={'force': True})
        record_api_failure(endpoint)
        raise

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.exceptions.ConnectionError, requests.exceptions.Timeout)),
    reraise=True
)
def call_pixelcade_text(message: str) -> None:
    """Call the Pixelcade API to display a text message."""
    endpoint = "pixelcade_text"
    if is_circuit_breaker_open(endpoint):
        logging.warning(f"Circuit breaker open for Pixelcade text API, skipping call", extra={'force': True})
        return
    
    url = f"{CONFIG['PIXELCADE_BASE_URL']}/text?message={quote_plus(message)}"
    try:
        logging.info(f"Calling Pixelcade text API with message '{message}', will display for {CONFIG['LOADING_DISPLAY_DURATION']} seconds", extra={'force': True})
        resp = requests.get(url, timeout=CONFIG['API_TIMEOUT'])
        resp.raise_for_status()
        record_api_success(endpoint)
    except Exception as e:
        logging.error(f"Pixelcade text widget call failed for message '{message}': {e}", extra={'force': True})
        record_api_failure(endpoint)
        raise

def safe_sleep(duration: int, stop_event: threading.Event, check_interval: int = 5) -> bool:
    """Sleep for duration seconds, checking stop_event every check_interval seconds."""
    elapsed = 0
    while elapsed < duration:
        sleep_time = min(check_interval, duration - elapsed)
        if stop_event.wait(sleep_time):
            return False
        elapsed += sleep_time
    return True

class PixelcadeSportsService(win32serviceutil.ServiceFramework):
    """Windows service to run the Pixelcade Sports Marquee script."""
    _svc_name_ = "PixelcadeSportsService"
    _svc_display_name_ = "Pixelcade Sports Marquee Service"
    _svc_description_ = "Runs the Pixelcade Sports Marquee script as a Windows service."

    def __init__(self, args):
        super().__init__(args)
        self.win32_stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.stop_event = threading.Event()
        self.running = True
        self.worker_thread = None

        try:
            if not win32api.GetVersionEx()[1] & 0x80:
                logging.warning("Service not running with administrative privileges, some operations may fail.", extra={'force': True})
        except Exception as e:
            logging.error(f"Failed to check admin privileges: {e}", extra={'force': True})

        log_dir = CONFIG['LOG_DIRECTORY']
        try:
            os.makedirs(log_dir, exist_ok=True)
            os.system(f'icacls "{log_dir}" /grant SYSTEM:F')
            test_file = os.path.join(log_dir, "test_write.txt")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            logging.info(f"Log directory {log_dir} created and writable", extra={'force': True})
        except Exception as e:
            logging.error(f"Failed to create or write to log directory {log_dir}: {e}", extra={'force': True})
            sys.exit(1)

        try:
            log_handler = logging.handlers.RotatingFileHandler(
                os.path.join(log_dir, CONFIG['LOG_FILENAME']),
                maxBytes=CONFIG['MAX_LOG_SIZE'],
                backupCount=CONFIG['BACKUP_COUNT']
            )
            log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            logging.getLogger().addHandler(log_handler)
            logging.info("File logging initialized", extra={'force': True})
        except Exception as e:
            logging.error(f"Failed to initialize file logging: {e}", extra={'force': True})


    def __del__(self):
        """Cleanup resources when service is destroyed."""
        try:
            if hasattr(self, 'win32_stop_event') and self.win32_stop_event:
                win32api.CloseHandle(self.win32_stop_event)
        except Exception:
            pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.ConnectionError, requests.exceptions.Timeout)),
        reraise=True
    )
    def check_pixelcade_availability(self) -> bool:
        """Check if the Pixelcade API is available."""
        endpoint = "pixelcade_health"
        if is_circuit_breaker_open(endpoint):
            logging.warning(f"Circuit breaker open for Pixelcade health check", extra={'force': True})
            return False
        
        try:
            resp = requests.get(f"{CONFIG['PIXELCADE_BASE_URL']}/weather", timeout=CONFIG['API_TIMEOUT'])
            resp.raise_for_status()
            logging.info("Pixelcade API is available.", extra={'force': True})
            record_api_success(endpoint)
            return True
        except Exception as e:
            logging.warning(f"Pixelcade API unavailable at {CONFIG['PIXELCADE_BASE_URL']}, continuing: {e}", extra={'force': True})
            record_api_failure(endpoint)
            return False

    def SvcStop(self):
        """Stop the Windows service."""
        try:
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            logging.info("PixelcadeSportsService stopping...", extra={'force': True})
            
            self.running = False
            self.stop_event.set()
            win32event.SetEvent(self.win32_stop_event)
            
            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=CONFIG['WORKER_THREAD_TIMEOUT'])
                if self.worker_thread.is_alive():
                    logging.warning("Worker thread did not stop within timeout", extra={'force': True})
                else:
                    logging.info("Worker thread stopped.", extra={'force': True})
                    
        except Exception as e:
            logging.error(f"Error stopping service: {e}", extra={'force': True})
            raise

    def SvcDoRun(self):
        """Run the Windows service."""
        try:
            
            logging.info(f"Pixelcade Sports Service v{__version__} ({__version_date__}) - Script execution started", extra={'force': True})
            logging.info(f"Displaying loading message: '{CONFIG['LOADING_MESSAGE']}'", extra={'force': True})
            try:
                call_pixelcade_text(CONFIG['LOADING_MESSAGE'])
            except Exception as e:
                logging.warning(f"Failed to display loading message: {e}", extra={'force': True})
            
            logging.info("Starting %d-second delay for internet connectivity at %s", CONFIG['STARTUP_DELAY'], datetime.now(timezone.utc), extra={'force': True})
            if not safe_sleep(CONFIG['STARTUP_DELAY'], self.stop_event):
                logging.info("Service stop requested during startup delay", extra={'force': True})
                return
            logging.info("Completed %d-second delay at %s", CONFIG['STARTUP_DELAY'], datetime.now(timezone.utc), extra={'force': True})
            
            for attempt in range(1, CONFIG['CONNECTIVITY_MAX_ATTEMPTS'] + 1):
                if not self.running:
                    return
                    
                try:
                    socket.create_connection((CONFIG['CONNECTIVITY_TEST_HOST'], CONFIG['CONNECTIVITY_TEST_PORT']), timeout=5)
                    logging.info("TCP connectivity confirmed.", extra={'force': True})
                    socket.getaddrinfo("site.api.espn.com", 443, socket.AF_INET, socket.SOCK_STREAM)
                    logging.info("DNS resolution for site.api.espn.com confirmed.", extra={'force': True})
                    break
                except OSError as e:
                    logging.warning(f"Connectivity check attempt {attempt}/{CONFIG['CONNECTIVITY_MAX_ATTEMPTS']} failed: {e}", extra={'force': True})
                    if attempt == CONFIG['CONNECTIVITY_MAX_ATTEMPTS']:
                        logging.error("No internet or DNS connectivity after retries. Aborting startup.", extra={'force': True})
                        self.ReportServiceStatus(win32service.SERVICE_STOPPED)
                        return
                    if not safe_sleep(CONFIG['CONNECTIVITY_RETRY_DELAY'], self.stop_event):
                        logging.info("Service stop requested during connectivity checks", extra={'force': True})
                        return
            
            if not self.check_pixelcade_availability():
                logging.warning("Service continuing despite Pixelcade API unavailability.", extra={'force': True})
            
            self.worker_thread = threading.Thread(target=self.main_loop)
            self.worker_thread.daemon = True
            self.worker_thread.start()
            logging.info("Main loop started.", extra={'force': True})
            
            win32event.WaitForSingleObject(self.win32_stop_event, win32event.INFINITE)
            
        except Exception as e:
            logging.error(f"Error running service: {e}", extra={'force': True})
            self.ReportServiceStatus(win32service.SERVICE_STOPPED)
            raise

    def main_loop(self):
        """Main loop to fetch sports schedules and display on Pixelcade."""
        while self.running and not self.stop_event.is_set():
            try:
                logging.info("Starting new schedule fetch cycle...", extra={'force': True})
                cycle_start_time = time.time()
                active_leagues = []

                for league in CONFIG['ESPN_API_ENDPOINTS']:
                    if not self.running or self.stop_event.is_set():
                        break
                        
                    if not CONFIG['LEAGUE_TOGGLES'].get(league, False):
                        logging.info(f"Skipping {league.upper()} as it is disabled in configuration.", extra={'force': True})
                        continue
                        
                    events = fetch_schedule(league)
                    if events is None:
                        continue
                    logging.info(f"Fetched {len(events)} events for {league}", extra={'force': True})

                    if has_relevant_games(events):
                        logging.info(f"{league.upper()} has relevant games.", extra={'force': True})
                        filtered = [e for e in events if is_event_within_24_hours(e)]
                        if filtered:
                            active_leagues.append((league, filtered))
                    else:
                        logging.info(f"No relevant games for {league.upper()}.", extra={'force': True})

                if not active_leagues:
                    logging.info("No active leagues found. Displaying weather only.", extra={'force': True})
                    weather_cycles = CONFIG['REFRESH_INTERVAL'] // CONFIG['WEATHER_DISPLAY_DURATION']
                    for _ in range(weather_cycles):
                        if not self.running or self.stop_event.is_set():
                            break
                        try:
                            call_pixelcade_weather()
                        except Exception as e:
                            logging.error(f"Failed to call weather API: {e}", extra={'force': True})
                        if not safe_sleep(CONFIG['WEATHER_DISPLAY_DURATION'], self.stop_event):
                            break
                    continue

                while (time.time() - cycle_start_time < CONFIG['REFRESH_INTERVAL'] and 
                       self.running and not self.stop_event.is_set()):
                    
                    for league, events in active_leagues:
                        if not self.running or self.stop_event.is_set():
                            break
                            
                        num_games = len(events)
                        display_seconds = calculate_display_time(num_games)
                        
                        try:
                            call_pixelcade_sports(league, display_seconds)
                        except Exception as e:
                            logging.error(f"Failed to call sports API for {league}: {e}", extra={'force': True})
                        
                        if not safe_sleep(display_seconds, self.stop_event):
                            break

                    if not self.running or self.stop_event.is_set():
                        break

                    try:
                        call_pixelcade_weather()
                    except Exception as e:
                        logging.error(f"Failed to call weather API: {e}", extra={'force': True})
                    
                    if not safe_sleep(CONFIG['WEATHER_DISPLAY_DURATION'], self.stop_event):
                        break

            except Exception as e:
                logging.error(f"Error in main loop: {e}", extra={'force': True})
                if not safe_sleep(CONFIG['ERROR_RETRY_DELAY'], self.stop_event):
                    break

        logging.info("Main loop exited", extra={'force': True})

if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(PixelcadeSportsService)