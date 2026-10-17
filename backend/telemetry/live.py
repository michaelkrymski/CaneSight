"""Opt-in CS-041 read-only projection; original native session routes unchanged.

Install only through this separate factory after review. No device credentials,
JPEGs, GPS, distances or unbounded capture-age estimates enter the projection.
"""
import argparse
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import secrets
from urllib.parse import urlsplit

import anyio
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response

from backend.app import check_json_depth, create_app
from backend.sessions import SessionManager, bearer, require_tls
from .dashboard import ASSETS, CSP, ROOT

COOKIE = '__Host-canesight_view'
LIVE_CSP = CSP.replace("connect-src 'none'", "connect-src 'self'")


class DashboardManager(SessionManager):
    """Observe already-admitted operations without consuming a peer's queue."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.projections = {}
        self.viewers = {}  # Hash -> (one session, absolute session-limited expiry).
        self.read_at = {}

    def create(self, request):
        with self.lock:
            pair = super().create(request)
            self.projections[pair['session_id']] = {
                'events': deque(maxlen=8), 'sources': {
                    role: dict(source_id=pair[role]['source_id'], boot_id=pair[role]['boot_id'],
                               packet_at=None, capture=None, model_version=None)
                    for role in ('phone', 'pi')}}
            return pair

    def _discard(self, session, code=4401):
        super()._discard(session, code)
        self.projections.pop(session.session_id, None)
        for key, (sid, _) in list(self.viewers.items()):
            if sid == session.session_id:
                self.viewers.pop(key)
                self.read_at.pop(key, None)

    def _observe(self, session, role, message, label):
        source = self.projections[session.session_id]['sources'][role]
        source['packet_at'] = self.clock()
        if message['type'] in ('frame_metadata', 'depth_observation', 'vision_observation'):
            source['capture'] = {key: message[key] for key in (
                'seq', 'capture_monotonic_ms', 'capture_utc')}
            source['capture']['frame_id'] = message.get('frame_id')
            source['capture']['type'] = message['type']
            if message['type'] == 'frame_metadata':
                source['model_version'] = None
            if message['type'] == 'vision_observation':
                source['model_version'] = message['model_version']
        self.projections[session.session_id]['events'].appendleft(label)

    def accept_frame(self, session, grant, metadata, jpeg):
        with self.lock:
            super().accept_frame(session, grant, metadata, jpeg)
            self._observe(session, 'pi', metadata, 'Pi frame accepted by backend')

    def relay(self, session, grant, connection, message, *, traffic_limits=None):
        with self.lock:
            super().relay(session, grant, connection, message, traffic_limits=traffic_limits)
            self._observe(session, grant.role, message, grant.role + ' packet admitted')

    def take_vision(self, session, grant, connection):
        with self.lock:
            message = super().take_vision(session, grant, connection)
            if message is not None:
                self._observe(session, 'pi', message, 'Vision offered to native socket; receipt unconfirmed')
            return message

    def issue_viewer(self, session_id):
        with self.lock:
            self.expire()
            if session_id not in self.sessions:
                raise HTTPException(404, 'Session not found')
            now = self.clock()
            self.viewers = {key: value for key, value in self.viewers.items() if value[1] > now}
            self.read_at = {key: value for key, value in self.read_at.items() if key in self.viewers}
            if len(self.viewers) >= 16:
                raise HTTPException(503, 'Viewer capacity reached')
            token = secrets.token_urlsafe(32)
            expires = min(now + 600, self.sessions[session_id].expires_at)
            self.viewers[hashlib.sha256(token.encode()).digest()] = (session_id, expires)
            return {'viewer_token': token, 'expires_in_seconds': max(1, int(expires - now))}

    def viewer(self, token):
        token = bearer('Bearer ' + (token or ''))
        with self.lock:
            self.expire()
            key = hashlib.sha256(token.encode()).digest()
            binding = self.viewers.get(key)
            if binding is None or binding[1] <= self.clock() or binding[0] not in self.sessions:
                self.viewers.pop(key, None)
                self.read_at.pop(key, None)
                raise HTTPException(401, 'Invalid or expired viewer')
            return binding

    def snapshot(self, token):
        with self.lock:
            session_id, _ = self.viewer(token)
            session = self.sessions[session_id]
            data = self.projections[session_id]
            now = self.clock()
            key = hashlib.sha256(token.encode()).digest()
            if now - self.read_at.get(key, float('-inf')) < .25:
                raise HTTPException(429, 'Viewer poll limit reached')
            self.read_at[key] = now
            sources = []
            for role, kind in (('phone', 'depth'), ('pi', 'vision')):
                source = data['sources'][role]
                connection = session.connections.get(role)
                packet_age = ((now - source['packet_at']) * 1000
                              if source['packet_at'] is not None and now >= source['packet_at'] else None)
                sources.append(dict(id=source['source_id'], boot_id=source['boot_id'], kind=kind,
                    connected=connection is not None and connection.close_code is None,
                    packet_age_ms=packet_age, capture=source['capture'],
                    model_version=source['model_version'], capture_age_upper_ms=None))
            return dict(version=1, session_id=session_id, mode=session.mode, sources=sources,
                events=list(data['events']), limitation='Capture age unknown: no verified device-to-backend clock mapping. No guidance or readiness verdict.')

    def revoke_viewer(self, token):
        with self.lock:
            try:
                token = bearer('Bearer ' + (token or ''))
            except HTTPException:
                return
            key = hashlib.sha256(token.encode()).digest()
            self.viewers.pop(key, None)
            self.read_at.pop(key, None)


async def closed_body(request, keys):
    if request.headers.get('content-type', '').split(';')[0] != 'application/json':
        raise HTTPException(415, 'JSON required')
    raw = bytearray()
    try:
        with anyio.fail_after(3):
            async for chunk in request.stream():
                raw.extend(chunk)
                if len(raw) > 512:
                    raise HTTPException(413, 'Request exceeds bound')
        def pairs(items):
            value = {}
            for key, item in items:
                if key in value:
                    raise ValueError()
                value[key] = item
            return value
        check_json_depth(raw)
        body = json.loads(raw, object_pairs_hook=pairs)
        if not isinstance(body, dict) or set(body) != set(keys) or any(not isinstance(v, str) for v in body.values()):
            raise ValueError()
        return body
    except (ValueError, UnicodeError, TimeoutError, RecursionError):
        raise HTTPException(400, 'Invalid request') from None


def install_dashboard(app, manager, origin):
    parsed = urlsplit(origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path or parsed.query or parsed.fragment):
        raise ValueError('Configure exact HTTPS dashboard origin, without path or credentials')

    def check(request, mutation=False):
        require_tls(request)
        if request.url.netloc != parsed.netloc or request.url.query:
            raise HTTPException(403, 'Dashboard origin/URL denied')
        if mutation and request.headers.get('origin') != origin:
            raise HTTPException(403, 'Same-origin request required')

    @app.middleware('http')
    async def headers(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith('/dashboard/') or request.url.path in ASSETS:
            response.headers.update({'Cache-Control': 'no-store', 'Content-Security-Policy': LIVE_CSP,
                'Referrer-Policy': 'no-referrer', 'X-Content-Type-Options': 'nosniff'})
        return response

    @app.post('/v1/dashboard-viewers')
    async def issue(request: Request):
        require_tls(request)
        if 'origin' in request.headers or request.url.query:
            raise HTTPException(403, 'Native operator request required')
        manager.authorize_operator(request.headers.get('authorization'))
        body = await closed_body(request, {'session_id'})
        return JSONResponse(manager.issue_viewer(body['session_id']), status_code=201,
                            headers={'Cache-Control': 'no-store'})

    @app.post('/dashboard/api/login')
    async def login(request: Request):
        check(request, True)
        body = await closed_body(request, {'viewer_token'})
        _, expires = manager.viewer(body['viewer_token'])
        response = Response(status_code=204)
        response.set_cookie(COOKIE, body['viewer_token'], max_age=max(1, int(expires-manager.clock())),
                            path='/', secure=True, httponly=True, samesite='strict')
        return response

    @app.get('/dashboard/api/snapshot')
    async def snapshot(request: Request):
        check(request)
        return JSONResponse(manager.snapshot(request.cookies.get(COOKIE)))

    @app.post('/dashboard/api/logout')
    async def logout(request: Request):
        check(request, True)
        manager.revoke_viewer(request.cookies.get(COOKIE))
        response = Response(status_code=204)
        response.delete_cookie(COOKIE, path='/', secure=True, httponly=True, samesite='strict')
        return response

    async def asset(request: Request):
        check(request)
        filename, kind = ASSETS[request.url.path]
        content = (ROOT / filename).read_bytes()
        if filename == 'index.html':
            content = content.replace(b'data-feed="fixture"', b'data-feed="live"')
            content = content.replace(b'id="mode-label">Replay', b'id="mode-label">Unknown mode')
        return Response(content, media_type=kind)
    for path in ASSETS:
        app.add_api_route(path, asset, methods=['GET', 'HEAD'], include_in_schema=False)
    return app


def create_dashboard_app():
    manager = DashboardManager(os.environ.get('CANESIGHT_OPERATOR_TOKEN', ''))
    origin = os.environ.get('CANESIGHT_DASHBOARD_ORIGIN', '')
    worker = None
    weights = os.environ.get('CANESIGHT_VISION_WEIGHTS', '')
    if weights:
        if not Path(weights).is_absolute():
            raise ValueError('Absolute verified weight path required')
        from backend.inference_worker import InferenceWorker
        from backend.vision.observations import YoloFactory
        worker = InferenceWorker(YoloFactory(weights))
    return install_dashboard(create_app(session_manager=manager, inference_worker=worker), manager, origin)


def main():
    import uvicorn
    from backend.server import server_config
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18083)
    args = parser.parse_args()
    uvicorn.Server(server_config(app=create_dashboard_app(), port=args.port)).run()


if __name__ == '__main__':
    main()
