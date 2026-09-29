"""Authenticated WSGI view. Reads only the sidecar projection, never credentials."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
from .data import RUNTIME_TTL_SECONDS, freshness, read_json, utcnow

STATIC = Path(__file__).with_name('static')
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/app.css': ('app.css', 'text/css; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/favicon.svg': ('favicon.svg', 'image/svg+xml')}
HEADERS = [('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
           ('X-Frame-Options', 'DENY'), ('Referrer-Policy', 'no-referrer'),
           ('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")]


def view_snapshot(path, now=None):
    now = now or utcnow()
    data = read_json(path)
    if not data or data.get('schema') != 1:
        return {'schema': 1, 'available': False, 'server_time': now.isoformat(), 'error': 'SNAPSHOT_UNAVAILABLE'}
    # Recompute age at request time; a stopped collector cannot remain green.
    data = dict(data)
    data.update(available=True, server_time=now.isoformat(), collector=freshness(data.get('collector_observed_at'), now, 60))
    for section, ttl in (('runtime',RUNTIME_TTL_SECONDS), ('connections',900), ('account',60)):
        value = data.get(section)
        if not isinstance(value, dict):
            data[section] = None
            continue
        value.update(freshness(value.get('observed_at'), now, ttl))
        if not data['collector']['fresh'] or (section == 'account' and not data.get('account_read_ok')):
            value['fresh'] = False
        if section == 'runtime' and not value['fresh']:
            value['authority'] = 'UNKNOWN'
    return data


class Dashboard:
    def __init__(self, snapshot, auth):
        self.snapshot = Path(snapshot)
        self.auth = read_json(auth, 4096)
        if (not self.auth or self.auth.get('username') != 'operator'
                or not re.fullmatch('[0-9a-f]{64}', str(self.auth.get('password_sha256', '')))):
            raise ValueError('Dashboard credential file is missing or invalid')

    def authorized(self, environ):
        raw = environ.get('HTTP_AUTHORIZATION', '')
        if not isinstance(raw, str) or len(raw) > 512 or not raw.startswith('Basic '):
            return False
        try:
            user, password = base64.b64decode(raw[6:], validate=True).decode('utf-8').split(':', 1)
            digest = hashlib.sha256(password.encode()).hexdigest()
            return hmac.compare_digest(user.encode(), b'operator') and hmac.compare_digest(digest, self.auth['password_sha256'])
        except (ValueError, UnicodeError):
            return False

    def __call__(self, environ, start_response):
        method = environ.get('REQUEST_METHOD', 'GET')
        path = environ.get('PATH_INFO', '/')
        extra = []
        content_type = 'application/json; charset=utf-8'
        if method not in {'GET', 'HEAD'}:
            status, body = '405 Method Not Allowed', b'{"error":"READ_ONLY"}'
            extra = [('Allow','GET, HEAD')]
        elif not self.authorized(environ):
            status, body = '401 Unauthorized', b'{"error":"SIGN_IN_REQUIRED"}'
            extra = [('WWW-Authenticate', 'Basic realm="Dhan dashboard", charset="UTF-8"')]
        elif path == '/api/status':
            try:
                data = view_snapshot(self.snapshot)
                status = '200 OK' if data['available'] else '503 Service Unavailable'
                body = json.dumps(data, allow_nan=False).encode()
            except Exception:
                status, body = '503 Service Unavailable', b'{"error":"SNAPSHOT_UNAVAILABLE","available":false}'
        elif path in ASSETS:
            filename, content_type = ASSETS[path]
            status, body = '200 OK', (STATIC/filename).read_bytes()
        else:
            status, body = '404 Not Found', b'{"error":"NOT_FOUND"}'
        start_response(status, HEADERS + [('Content-Type', content_type), ('Content-Length', str(len(body)))] + extra)
        return [b'' if method == 'HEAD' else body]


def create_app():
    return Dashboard(os.environ.get('DHAN_DASHBOARD_SNAPSHOT', '/var/lib/sablestone-dhan-dashboard/snapshot.json'),
                     os.environ.get('DHAN_DASHBOARD_AUTH', '/etc/sablestone-dhan-dashboard/auth.json'))
