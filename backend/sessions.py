"""CS-029: operator-created, role-scoped paired sessions and TLS WebSockets.

Relay admission is authorization/shape/ordering, never a freshness verdict.
The original capture times survive unchanged. CS-030 owns age eligibility.
"""
import asyncio
import contextlib
import copy
import hmac
import json
import secrets
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Annotated, Literal

import anyio
from fastapi import HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from jsonschema import ValidationError
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .app import FrameIngress, SourceGrant, check_json_depth, protocol

Identity = Annotated[str, StringConstraints(pattern=r'^[A-Za-z0-9_-]{1,64}$')]


def drain(queue):
    while True:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            return


class SourceBinding(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_id: Identity
    boot_id: Identity


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['live', 'replay']
    phone: SourceBinding
    pi: SourceBinding
    ttl_seconds: Annotated[int, Field(strict=True, ge=1, le=600)] = 300


def require_tls(connection):
    # ASGI scheme comes from direct TLS or a narrowly trusted proxy. Never read
    # X-Forwarded-Proto ourselves: arbitrary clients must not select the scheme.
    if connection.scope['scheme'] not in ('https', 'wss'):
        raise HTTPException(403, 'HTTPS/WSS required')


def bearer(authorization):
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Bearer credential required')
    token = authorization[7:]
    if not 32 <= len(token) <= 128 or not token.isascii() or any(c.isspace() for c in token):
        raise HTTPException(401, 'Invalid credential')
    return token


@dataclass(eq=False)
class Connection:
    role: str
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=8), repr=False)
    close_code: int | None = None


@dataclass(eq=False)
class Session:
    session_id: str
    mode: str
    expires_at: float
    ingress: FrameIngress
    gate: object
    connections: dict = field(default_factory=dict, repr=False)
    probe: dict | None = None
    last_probe_at: float = float('-inf')


class SessionManager:
    """One process, at most eight pairs; operator reenrolls on restart/reboot.

    All mutable state is locked across frame-handler threads and the ASGI loop.
    Connection queues are used only on that one loop. Credentials are kept in
    memory and never included in repr/log/error strings or URL parameters.
    """
    def __init__(self, operator_token, *, clock=time.monotonic):
        bearer('Bearer ' + operator_token)
        self._operator_token = operator_token
        self.clock = clock
        self.lock = threading.RLock()
        self.sessions = {}

    def authorize_operator(self, authorization):
        token = bearer(authorization)
        if not hmac.compare_digest(token, self._operator_token):
            raise HTTPException(401, 'Invalid operator credential')

    def _discard(self, session, code=4401):
        for connection in session.connections.values():
            connection.close_code = code
            drain(connection.queue)
        session.probe = None
        # Frame validation in flight must recheck membership before commit.
        with session.ingress.lock:
            for mapping in (session.ingress.latest, session.ingress.ledger,
                            session.ingress.last_sequence, session.ingress.seen_ids):
                mapping.clear()
            session.ingress.grants = ()
        session.gate.active.clear()
        session.gate.last.clear()
        session.gate.retired.clear()
        self.sessions.pop(session.session_id, None)

    def expire(self):
        with self.lock:
            for session in list(self.sessions.values()):
                if session.expires_at <= self.clock():
                    self._discard(session)

    def configured(self):
        self.expire()
        with self.lock:
            return bool(self.sessions)

    def create(self, request):
        with self.lock:
            self.expire()
            if len(self.sessions) >= 8:
                raise HTTPException(503, 'Session capacity reached')
            if request.phone.source_id == request.pi.source_id:
                raise HTTPException(422, 'Phone and Pi need distinct source identities')
            session_id = secrets.token_hex(16)
            expires = self.clock() + request.ttl_seconds
            grants = [SourceGrant(secrets.token_urlsafe(32), session_id, binding.source_id,
                                  binding.boot_id, request.mode, expires, role)
                      for role, binding in (('phone', request.phone), ('pi', request.pi))]
            ingress = FrameIngress(grants, clock=self.clock)
            gate = protocol.SequenceGate(session_id, request.mode)
            for grant in grants:
                gate.enroll(grant.source_id, grant.boot_id,
                            {'depth_observation', 'heartbeat'} if grant.role == 'phone' else {'heartbeat'})
            session = Session(session_id, request.mode, expires, ingress, gate)
            self.sessions[session_id] = session
            response = {'schema_version': 1, 'session_id': session_id, 'mode': request.mode,
                        'expires_in_seconds': request.ttl_seconds}
            for grant in grants:
                response[grant.role] = {'token': grant.token, 'source_id': grant.source_id,
                                        'boot_id': grant.boot_id,
                                        'websocket_path': '/v1/telemetry' if grant.role == 'phone' else '/v1/events'}
            return response

    def _current(self, session):
        self.expire()
        if self.sessions.get(session.session_id) is not session:
            raise HTTPException(401, 'Session expired or revoked')

    def authenticate(self, authorization, role):
        token = bearer(authorization)
        with self.lock:
            self.expire()
            for session in self.sessions.values():
                for grant in session.ingress.grants:
                    if hmac.compare_digest(token, grant.token):
                        if grant.role != role:
                            raise HTTPException(403, 'Credential role does not allow this route')
                        return session, grant
        raise HTTPException(401, 'Invalid or expired credential')

    def revoke(self, session_id):
        with self.lock:
            self.expire()
            session = self.sessions.get(session_id)
            if session is None:
                raise HTTPException(404, 'Session not found')
            self._discard(session, 1000)

    def accept_frame(self, session, grant, metadata, jpeg):
        with self.lock:
            self._current(session)
            if grant not in session.ingress.grants:
                raise HTTPException(401, 'Credential no longer enrolled')
            session.ingress.accept(grant, metadata, jpeg)

    def attach(self, session, role):
        with self.lock:
            self._current(session)
            if role in session.connections:
                raise HTTPException(409, 'Role already connected')
            connection = Connection(role)
            session.connections[role] = connection
            return connection

    def detach(self, session, connection):
        with self.lock:
            if session.connections.get(connection.role) is connection:
                session.connections.pop(connection.role)
                session.probe = None
                # A transport interruption must not leave buffered observations
                # queued on a surviving peer. Reconnect keeps sequence marks.
                for peer in session.connections.values():
                    peer.close_code = 1012
                    drain(peer.queue)

    def relay(self, session, grant, connection, message):
        with self.lock:
            self._current(session)
            if connection.close_code is not None:
                raise ValueError('Connection invalidated')
            if message['session_id'] != session.session_id or message['mode'] != session.mode:
                raise ValueError('Wrong session/mode')
            kind = message['type']
            target = 'pi' if grant.role == 'phone' else 'phone'
            if kind in ('clock_probe', 'clock_reply'):
                bindings = {g.role: g for g in session.ingress.grants}
                expected = {'source_id': bindings['phone'].source_id,
                            'source_boot_id': bindings['phone'].boot_id,
                            'receiver_id': bindings['pi'].source_id,
                            'receiver_boot_id': bindings['pi'].boot_id}
                if any(message[key] != value for key, value in expected.items()):
                    raise ValueError('Wrong clock role/epoch')
                if kind == 'clock_probe':
                    if grant.role != 'pi' or self.clock() - session.last_probe_at < 1:
                        raise ValueError('Clock probe role/rate')
                    session.probe = {'message': copy.deepcopy(message), 'expires': self.clock() + 1}
                    session.last_probe_at = self.clock()
                else:
                    pending = session.probe
                    if (grant.role != 'phone' or pending is None or self.clock() >= pending['expires']
                            or message['t3_ms'] < message['t2_ms']
                            or any(message[k] != v for k, v in pending['message'].items() if k != 'type')):
                        raise ValueError('Unmatched or expired clock reply')
                    session.probe = None
            else:
                if message['source_id'] != grant.source_id or message['boot_id'] != grant.boot_id:
                    raise ValueError('Source impersonation')
                session.gate.admit(message)
            peer = session.connections.get(target)
            if peer is not None and peer.close_code is None:
                try:
                    peer.queue.put_nowait(copy.deepcopy(message))
                except asyncio.QueueFull:
                    peer.close_code = 1013
                    connection.close_code = 1013
                    raise ValueError('Slow consumer; observations invalidated') from None


async def session_body(request):
    if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'application/json':
        raise HTTPException(415, 'JSON required')
    raw = bytearray()
    try:
        with anyio.fail_after(5):
            async for chunk in request.stream():
                if len(raw) + len(chunk) > 2048:
                    raise HTTPException(413, 'Session request too large')
                raw.extend(chunk)
    except TimeoutError:
        raise HTTPException(408, 'Session request deadline exceeded') from None
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('Invalid constant')
    try:
        check_json_depth(raw)
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
        return SessionRequest.model_validate(value)
    except (ValueError, TypeError, RecursionError):
        raise HTTPException(422, 'Invalid session request') from None


async def socket_session(websocket, manager, role):
    session = connection = None
    tasks = []
    code = 1000
    try:
        require_tls(websocket)
        # Native phone/Pi clients use Authorization. Browser origins and all URL
        # parameters are rejected until a separate dashboard auth design exists.
        if websocket.query_params or websocket.headers.get('origin') is not None:
            raise HTTPException(403, 'Header-authenticated native clients only')
        session, grant = manager.authenticate(websocket.headers.get('authorization'), role)
        connection = manager.attach(session, role)
        await websocket.accept()
        receive = asyncio.create_task(websocket.receive())
        outgoing = asyncio.create_task(connection.queue.get())
        tasks = [receive, outgoing]
        while True:
            manager.expire()
            if connection.close_code is not None:
                code = connection.close_code
                break
            done, _ = await asyncio.wait(tasks, timeout=.1, return_when=asyncio.FIRST_COMPLETED)
            if receive in done:
                packet = receive.result()
                if packet['type'] == 'websocket.disconnect':
                    break
                raw = packet.get('bytes')
                if raw is None:
                    raw = packet.get('text', '').encode('utf-8')
                if len(raw) > 8192:
                    code = 1009
                    break
                check_json_depth(raw)
                message = protocol.parse_wire(raw)
                manager.relay(session, grant, connection, message)
                receive = asyncio.create_task(websocket.receive())
                tasks[0] = receive
            if outgoing in done:
                # Recheck expiry after wakeup, before sending buffered data.
                manager.expire()
                if connection.close_code is not None:
                    code = connection.close_code
                    break
                with anyio.fail_after(1):
                    await websocket.send_json(outgoing.result())
                outgoing = asyncio.create_task(connection.queue.get())
                tasks[1] = outgoing
    except HTTPException as error:
        code = {401: 4401, 403: 4403, 409: 4409}.get(error.status_code, 1008)
    except (ValueError, TypeError, ValidationError, RecursionError):
        code = 1008
    except TimeoutError:
        code = 1013
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        # ASGI shutdown/client cancellation still requires identity and buffer
        # cleanup before leaving the connection handler.
        pass
    finally:
        with anyio.CancelScope(shield=True):
            for task in tasks:
                task.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            if connection is not None:
                manager.detach(session, connection)
            with contextlib.suppress(RuntimeError, WebSocketDisconnect):
                await websocket.close(code=code)


def install_routes(app, manager):
    @app.post('/v1/sessions')
    async def create_session(request: Request):
        require_tls(request)
        manager.authorize_operator(request.headers.get('authorization'))
        body = await session_body(request)
        return JSONResponse(manager.create(body), status_code=201, headers={'Cache-Control': 'no-store'})

    @app.delete('/v1/sessions/{session_id}', status_code=204)
    def delete_session(session_id: str, request: Request):
        require_tls(request)
        manager.authorize_operator(request.headers.get('authorization'))
        manager.revoke(session_id)
        return Response(status_code=204, headers={'Cache-Control': 'no-store'})

    @app.websocket('/v1/telemetry')
    async def telemetry(websocket: WebSocket):
        await socket_session(websocket, manager, 'phone')

    @app.websocket('/v1/events')
    async def events(websocket: WebSocket):
        await socket_session(websocket, manager, 'pi')

    @asynccontextmanager
    async def lifecycle(app):
        async def sweep():
            while True:
                manager.expire()
                await asyncio.sleep(.1)
        cleanup = asyncio.create_task(sweep())
        try:
            yield
        finally:
            cleanup.cancel()
            await asyncio.gather(cleanup, return_exceptions=True)
            for session_id in list(manager.sessions):
                with contextlib.suppress(HTTPException):
                    manager.revoke(session_id)
    app.router.lifespan_context = lifecycle
