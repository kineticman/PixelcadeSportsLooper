import json
import os
import threading
from urllib.parse import urljoin

import requests as http_requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, 'config.json')

# Injected by main.py before the server starts
_config_lock: threading.Lock = None
_status: dict = None
_status_lock: threading.Lock = None


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
