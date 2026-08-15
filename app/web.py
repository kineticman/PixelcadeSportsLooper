import json
import glob
import logging
import os
import time
import threading
from urllib.parse import urljoin

import requests as http_requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, 'config.json')
HOST_DEV_PATH = os.environ.get('HOST_DEV_PATH', '/host-dev')
HOST_SYS_PATH = os.environ.get('HOST_SYS_PATH', '/host-sys')
PIXELCADE_USB_IDS = {('1b4f', '0008')}
DEFAULT_RECOVERY_HOLD_SECONDS = int(os.environ.get('PIXELCADE_RECOVERY_HOLD_SECONDS', '90'))
PIXELCADE_USB_ROOT = os.environ.get('PIXELCADE_USB_ROOT', '')

# Injected by main.py before the server starts
_config_lock: threading.Lock = None
_status: dict = None
_status_lock: threading.Lock = None
_recovery_lock = threading.Lock()


def init(config_lock, status, status_lock):
    global _config_lock, _status, _status_lock
    _config_lock = config_lock
    _status = status
    _status_lock = status_lock


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/config', methods=['GET'])
def get_config():
    with _config_lock:
        with open(CONFIG_PATH) as f:
            return jsonify(json.load(f))


@app.route('/api/config', methods=['POST'])
def save_config():
    data = request.get_json(force=True)
    if not isinstance(data, dict):
        return jsonify({'ok': False, 'error': 'Invalid JSON'}), 400
    with _config_lock:
        with open(CONFIG_PATH, 'w') as f:
            json.dump(data, f, indent=2)
    return jsonify({'ok': True})


@app.route('/api/status')
def get_status():
    with _status_lock:
        return jsonify(dict(_status))




def _set_recovery_hold(seconds, reason):
    hold_seconds = max(0, min(int(seconds), 300))
    hold_until = time.time() + hold_seconds
    with _status_lock:
        _status['pixelcade_healthy'] = False
        _status['pixelcade_recovery_hold_until'] = hold_until
        _status['pixelcade_recovery_hold_reason'] = reason
    return hold_seconds


def _read_text(path):
    with open(path) as f:
        return f.read().strip()


def _write_text(path, value):
    with open(path, 'w') as f:
        f.write(value)


def _discover_pixelcade_usb_devices():
    devices = []
    sys_root = os.path.realpath(HOST_SYS_PATH)
    tty_patterns = (
        os.path.join(HOST_SYS_PATH, 'class', 'tty', 'ttyACM*'),
        os.path.join(HOST_SYS_PATH, 'class', 'tty', 'ttyUSB*'),
    )

    for pattern in tty_patterns:
        for tty_path in glob.glob(pattern):
            tty = os.path.basename(tty_path)
            device_path = os.path.realpath(os.path.join(tty_path, 'device'))
            path = device_path

            while path.startswith(sys_root):
                vendor_path = os.path.join(path, 'idVendor')
                product_path = os.path.join(path, 'idProduct')
                if os.path.exists(vendor_path) and os.path.exists(product_path):
                    vendor = _read_text(vendor_path).lower()
                    product = _read_text(product_path).lower()
                    if (vendor, product) in PIXELCADE_USB_IDS:
                        devices.append({
                            'tty': tty,
                            'dev_path': os.path.join(HOST_DEV_PATH, tty),
                            'usb_id': f'{vendor}:{product}',
                            'sysfs_name': os.path.basename(path),
                            'authorized_path': os.path.join(path, 'authorized'),
                            'manufacturer': _read_text(os.path.join(path, 'manufacturer')) if os.path.exists(os.path.join(path, 'manufacturer')) else '',
                            'product_name': _read_text(os.path.join(path, 'product')) if os.path.exists(os.path.join(path, 'product')) else '',
                            'serial': _read_text(os.path.join(path, 'serial')) if os.path.exists(os.path.join(path, 'serial')) else '',
                        })
                    break

                parent = os.path.dirname(path)
                if parent == path:
                    break
                path = parent

    return devices


def _get_recovery_device():
    devices = _discover_pixelcade_usb_devices()
    if not devices:
        raise RuntimeError('No supported Pixelcade/BitPixel USB device found')
    return devices[0]



def _find_driver_bound_parent(path):
    sys_root = os.path.realpath(HOST_SYS_PATH)
    current = os.path.realpath(path)
    while current.startswith(sys_root):
        driver_path = os.path.join(current, 'driver')
        if os.path.exists(os.path.join(driver_path, 'unbind')) and os.path.exists(os.path.join(driver_path, 'bind')):
            return current, os.path.realpath(driver_path)
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    raise RuntimeError(f'No bindable driver parent found for {path}')


def _run_root_reset():
    root_name = PIXELCADE_USB_ROOT.strip()
    if not root_name:
        raise RuntimeError('PIXELCADE_USB_ROOT is not configured')
    if '/' in root_name or root_name in ('.', '..'):
        raise RuntimeError('Invalid PIXELCADE_USB_ROOT value')

    root_path = os.path.join(HOST_SYS_PATH, 'bus', 'usb', 'devices', root_name)
    if not os.path.exists(root_path):
        raise RuntimeError(f'USB root {root_name} is not available')

    device_path, driver_path = _find_driver_bound_parent(root_path)
    device_name = os.path.basename(device_path)
    _write_text(os.path.join(driver_path, 'unbind'), device_name)
    time.sleep(3)
    _write_text(os.path.join(driver_path, 'bind'), device_name)
    return {
        'tty': '',
        'dev_path': '',
        'usb_id': 'usb-root',
        'sysfs_name': root_name,
        'authorized_path': '',
        'manufacturer': '',
        'product_name': f'USB root {root_name}',
        'serial': '',
        'driver_device': device_name,
        'driver_path': driver_path,
    }


def _run_authorize_reset():
    device = _get_recovery_device()
    authorized_path = device['authorized_path']
    if not os.path.exists(authorized_path):
        raise RuntimeError(f'USB authorized control not found for {device["sysfs_name"]}')

    _write_text(authorized_path, '0')
    time.sleep(2)
    _write_text(authorized_path, '1')
    return device


def _run_driver_reset():
    device = _get_recovery_device()
    unbind_path = os.path.join(HOST_SYS_PATH, 'bus', 'usb', 'drivers', 'usb', 'unbind')
    bind_path = os.path.join(HOST_SYS_PATH, 'bus', 'usb', 'drivers', 'usb', 'bind')
    if not os.path.exists(unbind_path) or not os.path.exists(bind_path):
        raise RuntimeError('USB driver bind controls are not available')

    _write_text(unbind_path, device['sysfs_name'])
    time.sleep(2)
    _write_text(bind_path, device['sysfs_name'])
    return device


@app.route('/api/pixelcade-recovery/status')
def pixelcade_recovery_status():
    with _status_lock:
        hold_until = float(_status.get('pixelcade_recovery_hold_until') or 0)
        hold_reason = _status.get('pixelcade_recovery_hold_reason')
    return jsonify({
        'ok': True,
        'host_sys_available': os.path.isdir(HOST_SYS_PATH),
        'host_dev_available': os.path.isdir(HOST_DEV_PATH),
        'devices': _discover_pixelcade_usb_devices(),
        'usb_root': PIXELCADE_USB_ROOT,
        'usb_root_available': bool(PIXELCADE_USB_ROOT and os.path.exists(os.path.join(HOST_SYS_PATH, 'bus', 'usb', 'devices', PIXELCADE_USB_ROOT))),
        'recovery_hold_remaining': int(max(0, hold_until - time.time())),
        'recovery_hold_reason': hold_reason,
        'default_recovery_hold_seconds': DEFAULT_RECOVERY_HOLD_SECONDS,
    })


@app.route('/api/pixelcade-recovery', methods=['POST'])
def pixelcade_recovery():
    data = request.get_json(force=True)
    action = (data.get('action') or '').strip()
    hold_seconds = data.get('hold_seconds', DEFAULT_RECOVERY_HOLD_SECONDS)
    actions = {
        'authorize-reset': _run_authorize_reset,
        'driver-reset': _run_driver_reset,
        'root-reset': _run_root_reset,
    }

    if action not in actions:
        return jsonify({'ok': False, 'error': 'Unsupported recovery action'}), 400

    if not _recovery_lock.acquire(blocking=False):
        return jsonify({'ok': False, 'error': 'A recovery action is already running'}), 409

    try:
        device = actions[action]()
        applied_hold = _set_recovery_hold(hold_seconds, action)
        logging.warning(
            "Pixelcade recovery action %s completed for %s on %s; holding looper for %ss",
            action,
            device['usb_id'],
            device['sysfs_name'],
            applied_hold,
        )
        return jsonify({
            'ok': True,
            'action': action,
            'device': device,
            'recovery_hold_seconds': applied_hold,
            'message': f'Recovery command completed. SportsLooper will pause Pixelcade module output for {applied_hold}s.',
        })
    except PermissionError as e:
        return jsonify({'ok': False, 'error': f'Permission denied: {e}'}), 500
    except Exception as e:
        logging.exception("Pixelcade recovery action %s failed", action)
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        _recovery_lock.release()




@app.route('/api/pixelcade-command', methods=['POST'])
def send_pixelcade_command():
    data = request.get_json(force=True)
    base_url = (data.get('url') or '').rstrip('/')
    path = (data.get('path') or '').strip()
    if not base_url:
        return jsonify({'ok': False, 'error': 'No Pixelcade URL provided'}), 400
    if not path.startswith('/') or path.startswith('//') or '..' in path:
        return jsonify({'ok': False, 'error': 'Command path must start with / and stay relative'}), 400
    try:
        resp = http_requests.get(urljoin(f'{base_url}/', path.lstrip('/')), timeout=10)
        body = resp.text[:2000]
        return jsonify({
            'ok': resp.ok,
            'status': resp.status_code,
            'body': body,
        }), (200 if resp.ok else 502)
    except http_requests.exceptions.ConnectionError:
        return jsonify({'ok': False, 'error': f'Connection refused at {base_url}'})
    except http_requests.exceptions.Timeout:
        return jsonify({'ok': False, 'error': 'Timed out after 10s'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@app.route('/api/test-pixelcade', methods=['POST'])
def test_pixelcade():
    data = request.get_json(force=True)
    url = (data.get('url') or '').rstrip('/')
    if not url:
        return jsonify({'ok': False, 'error': 'No URL provided'})
    try:
        resp = http_requests.get(
            f"{url}/info",
            timeout=5,
        )
        resp.raise_for_status()
        return jsonify({'ok': True, 'status': resp.status_code})
    except http_requests.exceptions.ConnectionError:
        return jsonify({'ok': False, 'error': f'Connection refused at {url}'})
    except http_requests.exceptions.Timeout:
        return jsonify({'ok': False, 'error': 'Timed out after 5s'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})
