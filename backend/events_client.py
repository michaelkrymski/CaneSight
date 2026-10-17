"""Native Pi event consumer: verified WSS plus CS-030 local capture-age gate."""
import json
import ssl
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from jsonschema import ValidationError
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from .app import check_json_depth, protocol
from .freshness import CaptureAgeGate


class PairedEventsClient:
    def __init__(self, origin, pair, *, relative_drift_ppm=None, ssl_context=None, **gate_options):
        parsed = urlsplit(origin)
        if (parsed.scheme != 'wss' or not parsed.hostname or parsed.username or parsed.password
                or parsed.path not in ('','/') or parsed.query or parsed.fragment):
            raise ValueError('Use a WSS origin without credentials, query or path')
        self.origin = origin.rstrip('/')
        self._token = pair['pi']['token']
        self.ssl_context = ssl_context or ssl.create_default_context()
        if not self.ssl_context.check_hostname or self.ssl_context.verify_mode != ssl.CERT_REQUIRED:
            raise ValueError('Certificate and hostname verification required')
        self.gate = CaptureAgeGate.for_pair(pair, relative_drift_ppm=relative_drift_ppm, **gate_options)
        self.socket = None

    @asynccontextmanager
    async def connection(self):
        if self.socket is not None:
            raise RuntimeError('Client already connected')
        try:
            async with connect(self.origin+'/v1/events', ssl=self.ssl_context,
                               additional_headers={'Authorization': 'Bearer '+self._token},
                               proxy=None, max_size=8192, open_timeout=5, close_timeout=1) as socket:
                self.socket = socket
                yield self
        finally:
            self.socket = None
            self.gate.interrupt()

    async def probe(self, source_id):
        if self.socket is None:
            raise RuntimeError('Connect before probing')
        message = self.gate.start_probe(source_id)
        await self.socket.send(json.dumps(message, allow_nan=False))
        return message

    async def receive_once(self):
        """Read one authenticated packet; None is no eligible observation.

        Keep current()/expire() running in an independent policy loop; this
        receive may block without extending any stored capture-age deadline.
        """
        if self.socket is None:
            raise RuntimeError('Client is disconnected')
        try:
            raw = await self.socket.recv()
        except ConnectionClosed:
            self.gate.interrupt()
            raise
        if isinstance(raw, str):
            raw = raw.encode('utf-8')
        try:
            check_json_depth(raw)
            message = protocol.parse_wire(raw)
            if message['type'] == 'clock_reply':
                self.gate.finish_probe(message)
                return None
            return self.gate.receive(message)
        except (ValueError, TypeError, ValidationError, OverflowError):
            # Rejected packets cannot become guidance or reset replay state.
            return None
