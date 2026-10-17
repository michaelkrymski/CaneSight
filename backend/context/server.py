"""Opt-in context factory; existing backend factory/routes remain unchanged."""
import asyncio
from contextlib import asynccontextmanager
import json
import os
import re

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from backend.app import check_json_depth, parse_metadata, read_parts, validate_jpeg
from backend.server import create_session_app
from backend.sessions import require_tls
from .provider import Gemini, strict_json
from .service import ContextBusy, ContextService, ContextUnavailable


def parse_context(raw):
    if len(raw) > 8192:
        raise ValueError('Metadata too large')
    check_json_depth(raw)
    value = strict_json(raw)
    if (type(value) is not dict or set(value) != {'request_id', 'consent', 'frame'}
            or value['consent'] is not True or type(value['request_id']) is not str
            or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value['request_id'])):
        raise ValueError('Invalid context request')
    frame = parse_metadata(json.dumps(value['frame']).encode())
    return value['request_id'], frame


def install_context(app, service):
    manager = app.state.sessions
    if manager is None:
        raise ValueError('Context requires accepted paired sessions')
    app.state.context = service
    previous = app.router.lifespan_context

    def valid_sessions():
        manager.expire()
        with manager.lock:
            return set(manager.sessions)

    @asynccontextmanager
    async def lifespan(app):
        async with previous(app) as state:
            await service.verify()
            async def sweep():
                while True:
                    service.prune(valid_sessions())
                    await asyncio.sleep(.05)
            cleanup = asyncio.create_task(sweep())
            try:
                yield state
            finally:
                cleanup.cancel()
                await asyncio.gather(cleanup, return_exceptions=True)
                await service.close()
    app.router.lifespan_context = lifespan

    @app.get('/v1/context/status')
    async def status(request: Request):
        require_tls(request)
        manager.authenticate(request.headers.get('authorization'), 'pi')
        return JSONResponse({'available': service.ready, 'model': service.model},
                            headers={'Cache-Control': 'no-store'})

    @app.post('/v1/context')
    async def describe(request: Request):
        require_tls(request)
        authorization = request.headers.get('authorization')
        session, grant = manager.authenticate(authorization, 'pi')
        try:
            slot = service.reserve(session.session_id, valid_sessions())
        except ContextBusy:
            raise HTTPException(429, 'Context capacity or cooldown reached',
                                headers={'Retry-After': '10'}) from None
        except ContextUnavailable:
            raise HTTPException(503, 'Description unavailable') from None
        waiter = None
        try:
            async with asyncio.timeout_at(slot.deadline):
                raw, jpeg = await read_parts(request)
                try:
                    request_id, frame = parse_context(raw)
                except Exception:
                    raise HTTPException(422, 'Invalid context metadata or consent') from None
                if any(frame[key] != getattr(grant, key) for key in
                       ('session_id', 'source_id', 'boot_id', 'mode')):
                    raise HTTPException(403, 'Context source binding mismatch')
                await run_in_threadpool(validate_jpeg, jpeg, frame)
                service.bind_id(slot, request_id)
                waiter = asyncio.create_task(service.describe(slot, jpeg))
                while not waiter.done():
                    manager.authenticate(authorization, 'pi')
                    if await request.is_disconnected():
                        raise HTTPException(499, 'Context request cancelled')
                    await asyncio.wait({waiter}, timeout=.05)
                value = await waiter
                manager.authenticate(authorization, 'pi')
                if asyncio.get_running_loop().time() >= slot.deadline:
                    raise ContextUnavailable()
                return JSONResponse({'request_id': request_id, 'frame': frame,
                    'model': service.model, 'description': value,
                    'capture_age_bounded': False}, headers={'Cache-Control': 'no-store'})
        except ContextBusy:
            raise HTTPException(409, 'Context request already used') from None
        except (ContextUnavailable, TimeoutError):
            raise HTTPException(503, 'Description unavailable') from None
        except asyncio.CancelledError:
            # Revocation/sweep cancels a child; never turn that into a result.
            raise HTTPException(503, 'Description unavailable') from None
        finally:
            if waiter is not None:
                waiter.cancel()
                await asyncio.gather(waiter, return_exceptions=True)
            service.release(slot)
    return app


def create_context_app():
    model = os.environ.get('CANESIGHT_GEMINI_MODEL', '')
    Gemini(model)  # Validate configuration without network or credential output.
    if not os.environ.get('GEMINI_API_KEY'):
        raise RuntimeError('Configure server-only GEMINI_API_KEY')
    return install_context(create_session_app(), ContextService(model))


def main():
    import argparse
    import uvicorn
    from backend.server import server_config
    parser = argparse.ArgumentParser(description='Opt-in context server with accepted transport bounds')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--forwarded-allow-ips', default='127.0.0.1')
    args = parser.parse_args()
    config = server_config(app=create_context_app(), host=args.host, port=args.port,
                           forwarded_allow_ips=args.forwarded_allow_ips)
    uvicorn.Server(config).run()


if __name__ == '__main__':
    main()
