"""CS-028 ingestion skeleton. No inference, source enrollment or motor policy."""
import copy
import hmac
import importlib.util
import io
import re
import sys
import threading
import time
from collections import deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import anyio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from jsonschema import ValidationError
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from .limits import TrafficGuard, TrafficLimits

# Import the accepted reference without changing the protected contract package.
_path = Path(__file__).resolve().parents[1] / 'shared/protocol/v1/reference.py'
_spec = importlib.util.spec_from_file_location('canesight_ingestion_contract_v1', _path)
protocol = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = protocol
_spec.loader.exec_module(protocol)

MAX_JPEG = 1_000_000
MAX_BODY = 1_024_000  # JPEG + 8192-byte JSON + bounded multipart overhead.
MAX_JSON_DEPTH = 12
MAX_FRAMES_PER_EPOCH = 4096  # New authorized session required after this bound.


@dataclass(frozen=True)
class SourceGrant:
    """Trusted adapter input, never enrollment data taken from an upload.

    CS-029 supplies authenticated enrollment/rotation. Tokens must be random,
    short lived and delivered outside Git; the replay factory uses an env var.
    """
    token: str = field(repr=False)
    session_id: str
    source_id: str
    boot_id: str
    mode: str
    expires_at: float
    role: str = 'pi'


@dataclass(frozen=True)
class AcceptedFrame:
    metadata: dict
    jpeg: bytes = field(repr=False)


class FrameIngress:
    """Bounded handoff seam for CS-031, not an inference worker.

    Two metadata ledger records and only the latest JPEG per enrolled source.
    State and replay high-water marks live for the fixed grant lifetime. Run one
    process; CS-029 must replace this with shared state before multiworker use.
    """
    def __init__(self, grants=(), *, clock=time.monotonic):
        self.grants = tuple(grants)
        self.clock = clock
        keys = [(g.session_id, g.source_id) for g in self.grants]
        if len(keys) > 16 or len(set(keys)) != len(keys):
            raise ValueError('At most 16 distinct enrolled sources')
        if len({g.token for g in self.grants}) != len(keys):
            raise ValueError('Each enrolled source needs a distinct credential')
        for grant in self.grants:
            if (len(grant.token) < 32 or not grant.token.isascii()
                    or any(c.isspace() for c in grant.token)
                    or not 0 < grant.expires_at - clock() <= 3600):
                raise ValueError('Use a bounded, short-lived credential')
            for identity in (grant.session_id, grant.source_id, grant.boot_id):
                if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', identity):
                    raise ValueError('Invalid enrolled identity')
            if grant.mode not in ('live', 'replay') or grant.role not in ('pi', 'phone', 'dashboard'):
                raise ValueError('Invalid enrolled role/mode')
        self.lock = threading.Lock()
        self.latest = {}
        self.ledger = {}
        self.last_sequence = {}
        self.seen_ids = {}

    def _expire(self):
        for grant in self.grants:
            if grant.expires_at <= self.clock():
                key = (grant.session_id, grant.source_id)
                for mapping in (self.latest, self.ledger, self.last_sequence, self.seen_ids):
                    mapping.pop(key, None)

    def authenticate(self, authorization):
        if not authorization or not authorization.startswith('Bearer '):
            raise HTTPException(401, 'Credential required', headers={'WWW-Authenticate': 'Bearer'})
        token = authorization[7:]
        with self.lock:
            self._expire()
            grant = next((g for g in self.grants if hmac.compare_digest(token.encode(), g.token.encode())), None)
            if grant is None or grant.expires_at <= self.clock():
                raise HTTPException(401, 'Invalid or expired credential')
            if grant.role != 'pi':
                raise HTTPException(403, 'Pi source role required')
            return grant

    def accept(self, grant, metadata, jpeg):
        with self.lock:
            self._expire()
            if grant.expires_at <= self.clock():
                raise HTTPException(401, 'Expired credential')
            if any(metadata[k] != getattr(grant, k) for k in ('session_id', 'source_id', 'mode')):
                raise HTTPException(403, 'Source/session/mode does not match enrollment')
            if metadata['boot_id'] != grant.boot_id:
                raise HTTPException(409, 'Epoch does not match enrollment')
            key = (grant.session_id, grant.source_id)
            seen = self.seen_ids.get(key, set())
            if metadata['seq'] <= self.last_sequence.get(key, -1) or metadata['frame_id'] in seen:
                raise HTTPException(409, 'Duplicate or reordered frame')
            if len(seen) >= MAX_FRAMES_PER_EPOCH:
                raise HTTPException(409, 'Epoch frame bound reached; create a new authorized session')
            # Commit only after the entire JPEG/metadata pair has been validated.
            self.last_sequence[key] = metadata['seq']
            self.seen_ids.setdefault(key, set()).add(metadata['frame_id'])
            self.ledger.setdefault(key, deque(maxlen=2)).append(copy.deepcopy(metadata))
            self.latest[key] = AcceptedFrame(copy.deepcopy(metadata), jpeg)

    def configured(self):
        with self.lock:
            self._expire()
            return any(g.role == 'pi' and g.expires_at > self.clock() for g in self.grants)


def check_json_depth(raw):
    # Bound nesting before json.loads materializes nested objects. Strings and
    # escaped quotes must not contribute structural brackets.
    depth, quoted, escaped = 0, False, False
    for char in raw:
        if quoted:
            if escaped:
                escaped = False
            elif char == 92:
                escaped = True
            elif char == 34:
                quoted = False
        elif char == 34:
            quoted = True
        elif char in (123, 91):
            depth += 1
            if depth > MAX_JSON_DEPTH:
                raise ValueError('JSON nesting limit')
        elif char in (125, 93):
            depth -= 1
def parse_metadata(raw):
    check_json_depth(raw)
    metadata = protocol.parse_wire(raw)
    if metadata['type'] != 'frame_metadata':
        raise ValueError('Expected frame metadata')
    return metadata


def validate_jpeg(jpeg, metadata):
    if len(jpeg) > MAX_JPEG:
        raise HTTPException(413, 'JPEG exceeds byte limit')
    if len(jpeg) != metadata['jpeg_bytes']:
        raise HTTPException(422, 'JPEG byte count mismatch')
    try:
        with Image.open(io.BytesIO(jpeg), formats=['JPEG']) as image:
            width, height = image.size
            if not (1 <= width <= 1920 and 1 <= height <= 1080):
                raise HTTPException(413, 'Decoded dimensions exceed limits')
            if (width, height) != (metadata['image']['width'], metadata['image']['height']):
                raise HTTPException(422, 'JPEG dimensions mismatch')
            image.verify()
        # Header checks alone do not validate the compressed raster.
        with Image.open(io.BytesIO(jpeg), formats=['JPEG']) as image:
            image.load()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        raise HTTPException(422, 'Invalid JPEG') from None


async def read_parts(request):
    if request.headers.get('content-encoding', 'identity').lower() != 'identity':
        raise HTTPException(415, 'Content encoding unsupported')
    if request.headers.get('content-type', '').split(';')[0].strip().lower() != 'multipart/form-data':
        raise HTTPException(415, 'Multipart upload required')
    length = request.headers.get('content-length')
    if length is not None:
        if not length.isascii() or not length.isdigit():
            raise HTTPException(422, 'Invalid content length')
        if len(length) > 10 or int(length) > MAX_BODY:
            raise HTTPException(413, 'Request exceeds byte limit')
    chunks, size = [], 0
    try:
        with anyio.fail_after(5):
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_BODY:
                    raise HTTPException(413, 'Request exceeds byte limit')
                chunks.append(chunk)
    except TimeoutError:
        raise HTTPException(408, 'Upload deadline exceeded') from None
    body = b''.join(chunks)
    if length is not None and int(length) != len(body):
        raise HTTPException(422, 'Content length mismatch')
    async def receive():
        return {'type': 'http.request', 'body': body, 'more_body': False}
    bounded = Request(request.scope, receive)
    try:
        async with bounded.form(max_files=1, max_fields=1, max_part_size=8192) as form:
            if len(form.multi_items()) != 2 or set(form) != {'metadata', 'image'}:
                raise HTTPException(422, 'Exactly metadata and image parts required')
            metadata, image = form['metadata'], form['image']
            if not isinstance(metadata, str) or not isinstance(image, UploadFile):
                raise HTTPException(422, 'Metadata text and image file required')
            if image.content_type != 'image/jpeg':
                raise HTTPException(422, 'JPEG content type required')
            return metadata.encode('utf-8'), await image.read(MAX_JPEG + 1)
    except HTTPException:
        raise
    except Exception:
        # Multipart parser errors are deliberately bounded and never echoed.
        raise HTTPException(422, 'Invalid multipart upload') from None


def create_app(*, ingress=None, dependency_health=None, session_manager=None,
               inference_worker=None, traffic_limits=None):
    """Inject CS-029 grants and a truthful CS-031/034 health provider.

    Default app has no enrolled sources or model/worker. Health is liveness
    only; 202 means retained for ingestion, never fresh or inferred.
    """
    ingress = ingress if ingress is not None else FrameIngress()
    @asynccontextmanager
    async def lifespan(app):
        if inference_worker is not None:
            inference_worker.start()
        try:
            yield
        finally:
            if inference_worker is not None:
                await run_in_threadpool(inference_worker.stop)

    app = FastAPI(title='CaneSight ingestion', docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.ingress = ingress
    traffic_limits = traffic_limits if traffic_limits is not None else TrafficLimits()
    app.state.traffic_limits = traffic_limits
    app.add_middleware(TrafficGuard, limits=traffic_limits)
    app.state.inference_worker = inference_worker
    app.state.sessions = session_manager
    if session_manager is not None and inference_worker is not None:
        session_manager.bind_inference_worker(inference_worker)
    # Reject overload before reading/parsing/decompressing request bodies.
    slots = threading.BoundedSemaphore(4)

    @app.get('/healthz')
    def healthz():
        return {'status': 'alive'}

    @app.get('/readyz')
    def readyz():
        try:
            health = (inference_worker.health() if inference_worker is not None
                      else dependency_health() if dependency_health else {})
            checks = {'ingestion_configured': session_manager.configured() if session_manager else ingress.configured(),
                      'model_available': health.get('model_available') is True,
                      'worker_healthy': health.get('worker_healthy') is True}
        except Exception:
            checks = {'ingestion_configured': session_manager.configured() if session_manager else ingress.configured(),
                      'model_available': False, 'worker_healthy': False}
        ready = all(checks.values())
        return JSONResponse({'ready': ready, 'checks': checks}, status_code=200 if ready else 503)

    @app.post('/v1/frames', status_code=202)
    async def frames(request: Request):
        if session_manager is not None:
            from .sessions import require_tls
            require_tls(request)
            record, grant = session_manager.authenticate(request.headers.get('authorization'), 'pi')
        else:
            grant = ingress.authenticate(request.headers.get('authorization'))
        if not traffic_limits.frame_allowed(grant):
            raise HTTPException(429, 'Source frame rate exceeded', headers={'Retry-After': '1'})
        if not slots.acquire(blocking=False):
            raise HTTPException(503, 'Upload capacity reached')
        try:
            raw, jpeg = await read_parts(request)
            try:
                metadata = parse_metadata(raw)
            except (ValueError, ValidationError, TypeError, RecursionError):
                raise HTTPException(422, 'Invalid frame metadata') from None
            await run_in_threadpool(validate_jpeg, jpeg, metadata)
            if session_manager is not None:
                # Session admission and scheduling share the revocation lock.
                session_manager.accept_frame(record, grant, metadata, jpeg)
            else:
                ingress.accept(grant, metadata, jpeg)
                if inference_worker is not None:
                    # A 202 remains ingestion-only, never a freshness verdict.
                    inference_worker.submit(grant, metadata, jpeg)
            return {'schema_version': 1, 'frame_id': metadata['frame_id'], 'status': 'accepted'}
        finally:
            slots.release()

    if session_manager is not None:
        from .sessions import install_routes
        install_routes(app, session_manager)
    return app


app = create_app()
