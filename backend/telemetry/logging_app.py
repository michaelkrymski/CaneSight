"""CS-042 opt-in factory: native operator consent and isolated minimal logging.

Existing server/dashboard factories and device wire contracts are unchanged.
"""
from contextlib import asynccontextmanager
import math
import os
from pathlib import Path
import time
import uuid

import anyio
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from backend.app import create_app
from backend.sessions import require_tls
from .event_store import Event, stream_id
from .event_writer import EventWriter
from .live import DashboardManager, closed_body, install_dashboard

TYPES = {'frame_metadata': 'frame_accepted', 'depth_observation': 'depth_admitted',
         'heartbeat': 'heartbeat_admitted', 'vision_observation': 'vision_offered'}


class LoggingManager(DashboardManager):
    def __init__(self, token, writer, *, wall_clock=time.time, **kwargs):
        super().__init__(token, **kwargs)
        self.writer = writer
        self.wall_clock = wall_clock
        self.consent = {}  # At most eight active sessions; never persisted.

    def _discard(self, session, code=4401):
        self.consent.pop(session.session_id, None)
        super()._discard(session, code)

    def set_consent(self, session_id, action):
        with self.lock:
            self.expire()
            if session_id not in self.sessions:
                raise HTTPException(404, 'Session not found')
            binding = self.consent.get(session_id)
            if action == 'enable':
                if binding is not None and not binding['enabled']:
                    raise HTTPException(409, 'Withdrawn consent requires a new session')
                if binding is None:
                    binding = dict(stream_id=str(uuid.uuid4()), enabled=True, last={})
                    self.consent[session_id] = binding
                return dict(enabled=True, stream_id=binding['stream_id'], deletion_status='not_requested'), 200
            if action != 'disable':
                raise HTTPException(422, 'Use enable or disable')
            if binding is None:
                return dict(enabled=False, stream_id=None, deletion_status='not_requested'), 200
            # Stop before enqueueing deletion, including when the queue is full.
            binding['enabled'] = False
            return self.delete_stream(binding['stream_id'])

    def delete_stream(self, identifier):
        try:
            stream_id(identifier)
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(422, 'Invalid stream identifier') from None
        with self.lock:
            for binding in self.consent.values():
                if binding['stream_id'] == identifier:
                    binding['enabled'] = False
            queued = self.writer.delete(identifier)
            return dict(enabled=False, stream_id=identifier,
                        deletion_status='queued' if queued else 'retry_required'), 202 if queued else 503

    def _observe(self, session, role, message, label):
        super()._observe(session, role, message, label)
        binding = self.consent.get(session.session_id)
        if binding is None or not binding['enabled']:
            return
        kind = TYPES.get(message['type'])
        if kind is None:
            return
        # Logging failure is observational only. No exception/config/database
        # operation may escape back into already-admitted native processing.
        try:
            now = self.clock()
            wall = self.wall_clock()
            key = (role, kind)
            last = binding['last'].get(key)
            if (not math.isfinite(now) or not math.isfinite(wall)
                    or last is not None and now - last < 1):
                return
            binding['last'][key] = now
            self.writer.submit(Event(str(uuid.uuid4()), binding['stream_id'],
                                     int(wall // 60) * 60, session.mode, role, kind))
        except Exception:
            pass


def install_logging(app, manager):
    def operator(request):
        require_tls(request)
        if 'origin' in request.headers or request.url.query:
            raise HTTPException(403, 'Native operator request required')
        manager.authorize_operator(request.headers.get('authorization'))

    def response(result):
        body, status = result
        return JSONResponse(body, status_code=status, headers={'Cache-Control': 'no-store'})

    @app.post('/v1/event-logging/consent')
    async def consent(request: Request):
        operator(request)
        body = await closed_body(request, {'session_id', 'action'})
        return response(manager.set_consent(body['session_id'], body['action']))

    @app.post('/v1/event-logging/delete')
    async def delete(request: Request):
        operator(request)
        body = await closed_body(request, {'stream_id'})
        return response(manager.delete_stream(body['stream_id']))

    @app.post('/v1/event-logging/deletion-status')
    async def status(request: Request):
        operator(request)
        body = await closed_body(request, {'stream_id'})
        try:
            state = manager.writer.deletion_status(body['stream_id'])
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(422, 'Invalid stream identifier') from None
        return response((dict(deletion_status=state), 200))

    return app


def build_app(manager, origin, *, inference_worker=None):
    app = create_app(session_manager=manager, inference_worker=inference_worker)
    install_dashboard(app, manager, origin)
    return install_logging(app, manager)


def create_logging_app():
    config = Path(os.environ.get('CANESIGHT_EVENT_DB_CONFIG', ''))
    # No secrets or DB connection in this process. Invalid config is checked in
    # the worker; the optional writer may fail while native observations continue.
    if not config.is_absolute() or config.resolve().is_relative_to(Path(__file__).resolve().parents[2]):
        raise ValueError('Private absolute event database config outside checkout required')
    writer = EventWriter(str(config))
    manager = LoggingManager(os.environ.get('CANESIGHT_OPERATOR_TOKEN', ''), writer)
    inference = None
    weights = os.environ.get('CANESIGHT_VISION_WEIGHTS', '')
    if weights:
        if not Path(weights).is_absolute():
            raise ValueError('Absolute verified weight path required')
        from backend.inference_worker import InferenceWorker
        from backend.vision.observations import YoloFactory
        inference = InferenceWorker(YoloFactory(weights))
    app = build_app(manager, os.environ.get('CANESIGHT_DASHBOARD_ORIGIN', ''), inference_worker=inference)
    previous_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app):
        writer.start()
        try:
            async with previous_lifespan(app):
                yield
        finally:
            await anyio.to_thread.run_sync(writer.close)

    app.router.lifespan_context = lifespan
    return app


def main():
    import argparse
    import uvicorn
    from backend.server import server_config
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=18084)
    args = parser.parse_args()
    uvicorn.Server(server_config(app=create_logging_app(), port=args.port)).run()


if __name__ == '__main__':
    main()
