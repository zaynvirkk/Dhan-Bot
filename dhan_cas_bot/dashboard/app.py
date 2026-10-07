"""Authenticated WSGI view. Reads only the sidecar projection, never credentials."""
from __future__ import annotations

import base64
import hashlib
import hmac
from http.cookies import SimpleCookie, CookieError
import json
import os
from pathlib import Path
import re
import secrets
import time
import threading
from urllib.parse import parse_qs
from .data import RUNTIME_TTL_SECONDS, freshness, read_json, utcnow

STATIC = Path(__file__).with_name('static')
ASSETS = {'/': ('index.html', 'text/html; charset=utf-8'),
          '/app.css': ('app.css', 'text/css; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/stream.js': ('stream.js', 'text/javascript; charset=utf-8'),
          '/favicon.svg': ('favicon.svg', 'image/svg+xml')}
ORIGIN = 'https://dhan.34.100.255.111.sslip.io'
COOKIE = '__Host-dhan_dashboard'
SESSION_SECONDS = 8 * 60 * 60
PUBLIC_ASSETS = {'/login.css': ('login.css', 'text/css; charset=utf-8')}
HEADERS = [('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
           # no-referrer makes HTML form POST Origin null in Chromium. Keep
           # same-origin form provenance while suppressing cross-origin referrers.
           ('X-Frame-Options', 'DENY'), ('Referrer-Policy', 'same-origin'),
           ('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")]


def view_snapshot(path, now=None):
    now = now or utcnow()
    data = read_json(path)
    if not data or data.get('schema') != 1:
        return {'schema': 1, 'available': False, 'server_time': now.isoformat(), 'error': 'SNAPSHOT_UNAVAILABLE'}
    # Recompute age at request time; a stopped collector cannot remain green.
    data = dict(data)
    data.update(available=True, server_time=now.isoformat(), collector=freshness(data.get('collector_observed_at'), now, 60))
    for section, ttl in (('runtime',RUNTIME_TTL_SECONDS), ('connections',900), ('account',60), ('daily_monitor',90)):
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
        # Six streams per eight-thread worker leave room for login/status.
        self.stream_slots = threading.BoundedSemaphore(6)
        if (not self.auth or self.auth.get('username') != 'operator'
                or not re.fullmatch('[0-9a-f]{64}', str(self.auth.get('password_sha256', '')))):
            raise ValueError('Dashboard credential file is missing or invalid')

    def authorized(self, environ):
        # Browser sessions avoid HTTP auth prompts: some VPN extensions answer
        # every WWW-Authenticate challenge with their own proxy credentials.
        cookie = environ.get('HTTP_COOKIE', '')
        if isinstance(cookie, str) and len(cookie) <= 4096:
            try:
                jar = SimpleCookie(cookie)
                token = jar[COOKIE].value if COOKIE in jar else ''
                if re.fullmatch(r'v1\.[0-9]{10}\.[0-9a-f]{32}\.[0-9a-f]{64}', token):
                    payload, signature = token.rsplit('.', 1)
                    age = time.time() - int(payload.split('.')[1])
                    if 0 <= age < SESSION_SECONDS and hmac.compare_digest(signature, self.signature(payload)):
                        return True
            except (CookieError, ValueError):
                pass
        # Retain explicit Basic headers for read-only scripts; never challenge.
        raw = environ.get('HTTP_AUTHORIZATION', '')
        if not isinstance(raw, str) or len(raw) > 512 or not raw.startswith('Basic '):
            return False
        try:
            user, password = base64.b64decode(raw[6:], validate=True).decode('utf-8').split(':', 1)
            return self.valid_password(user, password)
        except (ValueError, UnicodeError):
            return False

    def valid_password(self, user, password):
        digest = hashlib.sha256(password.encode()).hexdigest()
        return hmac.compare_digest(user.encode(), b'operator') and hmac.compare_digest(digest, self.auth['password_sha256'])

    def signature(self, payload):
        # The verifier is a server-only 256-bit secret, shared across workers.
        # Domain separation prevents accepting a signature for another purpose.
        return hmac.new(bytes.fromhex(self.auth['password_sha256']),
                        ('dashboard-session:' + ORIGIN + ':' + payload).encode(), hashlib.sha256).hexdigest()

    def session_cookie(self, clear=False):
        payload = f'v1.{int(time.time())}.{secrets.token_hex(16)}'
        token = '' if clear else payload + '.' + self.signature(payload)
        return f'{COOKIE}={token}; Path=/; Secure; HttpOnly; SameSite=Strict; Max-Age={0 if clear else SESSION_SECONDS}'

    def login_page(self, error=False):
        return (STATIC/'login.html').read_text().replace('<!-- error -->',
            '<p class="error" role="alert">The username or password is incorrect. Please try again.</p>' if error else '').encode()

    def login(self, environ):
        if environ.get('HTTP_ORIGIN') != ORIGIN:
            return '403 Forbidden', b'{"error":"ORIGIN_REJECTED"}', [], 'application/json; charset=utf-8'
        try:
            size = int(environ.get('CONTENT_LENGTH', '0'))
            if not 0 < size <= 1024 or environ.get('CONTENT_TYPE', '').split(';')[0] != 'application/x-www-form-urlencoded':
                raise ValueError('Invalid form')
            body = environ['wsgi.input'].read(size)
            if len(body) != size:
                raise ValueError('Incomplete form')
            fields = parse_qs(body.decode('utf-8'), strict_parsing=True, max_num_fields=2)
            if set(fields) != {'username', 'password'} or any(len(v) != 1 for v in fields.values()):
                raise ValueError('Invalid fields')
        except (ValueError, KeyError, UnicodeError):
            return '400 Bad Request', b'{"error":"INVALID_FORM"}', [], 'application/json; charset=utf-8'
        if not self.valid_password(fields['username'][0], fields['password'][0]):
            return '401 Unauthorized', self.login_page(error=True), [], 'text/html; charset=utf-8'
        return '303 See Other', b'', [('Location', '/'), ('Set-Cookie', self.session_cookie())], 'text/html; charset=utf-8'

    def __call__(self, environ, start_response):
        method = environ.get('REQUEST_METHOD', 'GET')
        path = environ.get('PATH_INFO', '/')
        extra = []
        content_type = 'application/json; charset=utf-8'
        if method == 'POST' and path == '/login':
            status, body, extra, content_type = self.login(environ)
        elif method == 'POST' and path == '/logout':
            if environ.get('HTTP_ORIGIN') != ORIGIN:
                status, body = '403 Forbidden', b'{"error":"ORIGIN_REJECTED"}'
            else:
                status, body = '303 See Other', b''
                extra = [('Location', '/login'), ('Set-Cookie', self.session_cookie(clear=True))]
        elif method not in {'GET', 'HEAD'}:
            status, body = '405 Method Not Allowed', b'{"error":"READ_ONLY"}'
            extra = [('Allow','GET, HEAD')]
        elif path == '/login':
            if self.authorized(environ):
                status, body, extra = '303 See Other', b'', [('Location', '/')]
            else:
                status, body, content_type = '200 OK', self.login_page(), 'text/html; charset=utf-8'
        elif path in PUBLIC_ASSETS:
            filename, content_type = PUBLIC_ASSETS[path]
            status, body = '200 OK', (STATIC/filename).read_bytes()
        elif path == '/' and not self.authorized(environ):
            status, body, extra = '303 See Other', b'', [('Location', '/login')]
        elif not self.authorized(environ):
            status, body = '401 Unauthorized', b'{"error":"SIGN_IN_REQUIRED"}'
        elif path == '/api/events':
            headers = HEADERS + [('Content-Type', 'text/event-stream'), ('X-Accel-Buffering', 'no')]
            if method == 'HEAD':
                start_response('200 OK', headers)
                return [b'']
            if not self.stream_slots.acquire(blocking=False):
                start_response('503 Service Unavailable', HEADERS + [('Retry-After', '5')])
                return [b'']
            start_response('200 OK', headers)
            return EventStream(self, environ)
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


class EventStream:
    """Finite streams renew auth; close() also handles disconnect-before-first-read."""
    def __init__(self, app, environ):
        self.app, self.environ = app, dict(environ)
        self.deadline = time.monotonic() + 20
        self.first, self.closed = True, False
        self.previous = None
        self.previous_history = None

    def __iter__(self):
        return self

    def __next__(self):
        if self.closed:
            raise StopIteration
        if not self.first:
            time.sleep(1)
        self.first = False
        if not self.app.authorized(self.environ):
            self.close()
            return b'event: auth-required\ndata: {}\n\n'
        if time.monotonic() >= self.deadline:
            self.close()
            raise StopIteration
        try:
            data = view_snapshot(self.app.snapshot)
            # Unchanged observations need only a small timestamp update. Freshness
            # transitions and actual feed/account changes still send full data.
            def stable(value):
                if isinstance(value, dict):
                    return {k: stable(v) for k, v in value.items() if k not in {'server_time', 'age_seconds', 'collector_observed_at', 'observed_at'}}
                if isinstance(value, list):
                    return [stable(v) for v in value]
                return value
            evidence = stable(data)
            evidence.pop('collector', None)
            evidence['collector_fresh'] = data.get('collector', {}).get('fresh')
            digest = json.dumps(evidence, sort_keys=True, allow_nan=False)
            if digest == self.previous:
                times = {key: value.get('observed_at') for key in ('collector', 'runtime', 'account', 'connections', 'daily_monitor')
                         if isinstance(value := data.get(key), dict)}
                return ('event: pulse\ndata: '+json.dumps({'server_time': data['server_time'], 'observations': times})+'\n\n').encode()
            self.previous = digest
            history = data.get('history')
            if isinstance(history, dict) and history == self.previous_history:
                # Quote changes must not retransmit the whole retained journal.
                data.pop('history')
                data['history_unchanged'] = True
            else:
                self.previous_history = history
            return ('retry: 1000\ndata: '+json.dumps(data, allow_nan=False)+'\n\n').encode()
        except Exception:
            self.close()
            return b'data: {"available":false,"error":"SNAPSHOT_UNAVAILABLE"}\n\n'

    def close(self):
        if not self.closed:
            self.closed = True
            self.app.stream_slots.release()


def create_app():
    return Dashboard(os.environ.get('DHAN_DASHBOARD_SNAPSHOT', '/var/lib/sablestone-dhan-dashboard/snapshot.json'),
                     os.environ.get('DHAN_DASHBOARD_AUTH', '/etc/sablestone-dhan-dashboard/auth.json'))
