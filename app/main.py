import logging
import os
import signal
import sys
import threading
import time
from logging.handlers import RotatingFileHandler

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            os.path.join(SCRIPT_DIR, 'sportslooper.log'),
            maxBytes=1_000_000,
            backupCount=5,
        ),
        logging.StreamHandler(sys.stdout),
    ],
)

logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('werkzeug.serving').setLevel(logging.ERROR)

from looper import config_lock, load_config, main_loop, pixelcade_serial_present, status, status_lock
import web

web.init(config_lock, status, status_lock)

stop_event = threading.Event()

AUTO_RECOVERY_POLL_SECONDS = 30
AUTO_RECOVERY_DEFAULT_AFTER = 120
AUTO_RECOVERY_DEFAULT_INTERVAL = 300


def _shutdown(sig, frame):
    logging.info(f"Received signal {sig}, shutting down")
    stop_event.set()
    sys.exit(0)


def auto_recovery_loop(stop_event):
    """Power-cycle the marquee's USB port when it stops answering enumeration.

    The kernel retries enumeration a few times, then gives up until something
    re-triggers the port, so a failed power-on leaves the marquee dark all day.
    Retry on a backoff schedule instead: port power-cycle first (the software
    equivalent of replugging the cable), then a root-hub reset.
    """
    missing_since = None
    attempts = 0

    while not stop_event.wait(AUTO_RECOVERY_POLL_SECONDS):
        try:
            cfg = load_config()
            pixelcade_cfg = cfg.get('pixelcade', {})

            if not pixelcade_cfg.get('auto_recovery', True):
                missing_since = None
                attempts = 0
                continue

            if pixelcade_serial_present():
                if missing_since is not None:
                    logging.info("Pixelcade serial device is back")
                missing_since = None
                attempts = 0
                with status_lock:
                    status['pixelcade_auto_recovery_state'] = 'idle'
                    status['pixelcade_auto_recovery_attempts'] = 0
                continue

            now = time.time()
            if missing_since is None:
                missing_since = now
                logging.warning("Pixelcade serial device is missing; auto-recovery armed")
                with status_lock:
                    status['pixelcade_auto_recovery_state'] = 'armed'
                continue

            after = max(30, int(pixelcade_cfg.get('auto_recovery_after_seconds', AUTO_RECOVERY_DEFAULT_AFTER)))
            interval = max(60, int(pixelcade_cfg.get('auto_recovery_interval_seconds', AUTO_RECOVERY_DEFAULT_INTERVAL)))
            if now - missing_since < after:
                continue

            with status_lock:
                last_attempt = status.get('pixelcade_auto_recovery_last_attempt') or 0
            if now - last_attempt < interval:
                continue

            attempts += 1
            order = ['port-reset', 'root-reset'] if attempts % 2 else ['root-reset', 'port-reset']
            device = None
            for action in order:
                try:
                    device, hold = web.run_auto_recovery(action)
                    logging.warning(
                        "Auto-recovery attempt %s: %s on %s (looper held %ss)",
                        attempts, action, device.get('sysfs_name'), hold,
                    )
                    break
                except Exception as e:
                    logging.warning("Auto-recovery attempt %s (%s) failed: %s", attempts, action, e)

            with status_lock:
                status['pixelcade_auto_recovery_last_attempt'] = now
                status['pixelcade_auto_recovery_attempts'] = attempts
                status['pixelcade_auto_recovery_last_action'] = action if device else None
                status['pixelcade_auto_recovery_state'] = 'recovering' if device else 'failed'
        except Exception:
            logging.exception("Auto-recovery watchdog iteration failed")


signal.signal(signal.SIGINT, _shutdown)
signal.signal(signal.SIGTERM, _shutdown)

looper_thread = threading.Thread(target=main_loop, args=(stop_event,), daemon=True, name='looper')
looper_thread.start()
logging.info("Looper thread started")

recovery_thread = threading.Thread(target=auto_recovery_loop, args=(stop_event,), daemon=True, name='auto-recovery')
recovery_thread.start()
logging.info("Auto-recovery watchdog started")

logging.info("Web admin available at http://0.0.0.0:6992")
web.app.run(host='0.0.0.0', port=6992, debug=False, use_reloader=False)
