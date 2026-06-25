import logging
import os
import signal
import sys
import threading
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

from looper import config_lock, main_loop, status, status_lock
import web

web.init(config_lock, status, status_lock)

stop_event = threading.Event()


def _shutdown(sig, frame):
    logging.info(f"Received signal {sig}, shutting down")
    stop_event.set()
    sys.exit(0)


signal.signal(signal.SIGINT, _shutdown)
signal.signal(signal.SIGTERM, _shutdown)

looper_thread = threading.Thread(target=main_loop, args=(stop_event,), daemon=True, name='looper')
looper_thread.start()
logging.info("Looper thread started")

logging.info("Web admin available at http://0.0.0.0:6992")
web.app.run(host='0.0.0.0', port=6992, debug=False, use_reloader=False)
