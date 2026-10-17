"""CS-027 Pi-only context HTTP adapter; never accepts a Gemini/operator key.

Network I/O is confined to one disposable child, so cancellation can close the
socket even when a peer stalls. The controller supplies the capture deadline.
"""
import copy
import json
import multiprocessing
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid

from .uploader import Frame, ID, NoRedirect

LABELS = frozenset(('person', 'chair', 'table', 'door', 'stairs', 'tree', 'vehicle',
    'sign', 'building', 'bicycle', 'bench', 'bag', 'dog', 'pole', 'wall', 'plant'))


class ContextError(Exception):
    def __init__(self, *, fatal=False):
        self.fatal = fatal
        super().__init__('Context unavailable')


def unique_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate field')
            result[key] = value
        return result
    def invalid(_):
        raise ValueError('Invalid number')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def validate_frame(frame):
    from backend.app import parse_metadata
    if not isinstance(frame, Frame) or type(frame.jpeg) is not bytes:
        raise ValueError('Use an original local camera frame')
    raw = json.dumps(frame.metadata, allow_nan=False).encode()
    if len(raw) > 7500 or not 0 < len(frame.jpeg) <= 1_000_000:
        raise ValueError('Frame exceeds limits')
    metadata = parse_metadata(raw)
    if metadata['jpeg_bytes'] != len(frame.jpeg):
        raise ValueError('Frame size mismatch')
    return metadata


def validate_reply(value, request_id, metadata):
    from backend.app import parse_metadata
    if (type(value) is not dict
            or set(value) != {'request_id', 'frame', 'model', 'description', 'capture_age_bounded'}
            or value['request_id'] != request_id or value['capture_age_bounded'] is not False
            or parse_metadata(json.dumps(value['frame'], allow_nan=False).encode()) != metadata
            or type(value['model']) is not str
            or not re.fullmatch(r'gemini-[A-Za-z0-9._-]{1,96}', value['model'])):
        raise ValueError('Context response binding mismatch')
    description = value['description']
    if (type(description) is not dict or set(description) != {'objects', 'uncertain'}
            or description['uncertain'] is not True or type(description['objects']) is not list
            or len(description['objects']) > 3
            or any(type(label) is not str or label not in LABELS for label in description['objects'])):
        raise ValueError('Unsupported context description')
    return copy.deepcopy(value)


def check_session(session):
    if type(session) is not dict or set(session) != {
            'base_url', 'session_id', 'source_id', 'boot_id', 'mode', 'token'}:
        raise ValueError('Use only the six-field Pi session credential')
    origin = urllib.parse.urlsplit(session['base_url'])
    if (origin.scheme != 'https' or not origin.hostname or origin.username or origin.password
            or origin.path not in ('', '/') or origin.query or origin.fragment):
        raise ValueError('Use the HTTPS origin without credentials/path/query')
    if (session['mode'] not in ('live', 'replay')
            or any(type(session[k]) is not str or not ID.fullmatch(session[k])
                   for k in ('session_id', 'source_id', 'boot_id'))
            or type(session['token']) is not str or not 32 <= len(session['token']) <= 128
            or not session['token'].isascii() or any(c.isspace() for c in session['token'])):
        raise ValueError('Invalid Pi session configuration')
    return dict(session)


class ContextHTTP:
    def __init__(self, session, *, ca_file=None, opener=None):
        self._session = check_session(session)
        self.url = self._session['base_url'].rstrip('/') + '/v1/context'
        self.opener = opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect(),
            urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=ca_file)))

    def send(self, request_id, frame, *, consent):
        if consent is not True or type(request_id) is not str or not ID.fullmatch(request_id):
            raise ContextError()
        try:
            metadata = validate_frame(frame)
            if any(metadata[k] != self._session[k] for k in ('session_id', 'source_id', 'boot_id', 'mode')):
                raise ContextError(fatal=True)
            raw = json.dumps({'request_id': request_id, 'consent': True, 'frame': metadata},
                             allow_nan=False, separators=(',', ':')).encode()
            boundary = uuid.uuid4().hex
            body = (f'--{boundary}\r\nContent-Disposition: form-data; name="metadata"\r\n\r\n'.encode()
                + raw + f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="context.jpg"\r\nContent-Type: image/jpeg\r\n\r\n'.encode()
                + frame.jpeg + f'\r\n--{boundary}--\r\n'.encode())
            if len(raw) > 8192 or len(body) > 1_024_000:
                raise ContextError()
            request = urllib.request.Request(self.url, data=body, method='POST', headers={
                'Authorization': 'Bearer ' + self._session['token'],
                'Content-Type': 'multipart/form-data; boundary=' + boundary})
            with self.opener.open(request, timeout=6) as response:
                payload = response.read(16_385)
                if response.status != 200 or len(payload) > 16_384:
                    raise ContextError(fatal=True)
                return validate_reply(unique_json(payload), request_id, metadata)
        except ContextError:
            raise
        except urllib.error.HTTPError as error:
            code = error.code
            error.close()
            raise ContextError(fatal=code in (401, 403, 409) or 300 <= code < 400) from None
        except Exception:
            raise ContextError() from None


def context_child(send, session, ca_file, request_id, frame):
    try:
        value = ContextHTTP(session, ca_file=ca_file).send(request_id, frame, consent=True)
    except ContextError as error:
        value = {'unavailable': True, 'fatal': error.fatal}
    except Exception:
        value = {'unavailable': True, 'fatal': False}
    try:
        send.send_bytes(json.dumps(value, allow_nan=False).encode())
    finally:
        send.close()


class ProcessRequest:
    """poll is nonblocking; cancel kills/reaps before permitting another job."""
    def __init__(self, session, ca_file, request_id, frame, *, target=context_child):
        ctx = multiprocessing.get_context('spawn')
        self._receive, send = ctx.Pipe(duplex=False)
        self._process = ctx.Process(target=target,
            args=(send, session, ca_file, request_id, frame), daemon=True)
        self._closed = False
        try:
            self._process.start()
        except Exception:
            self._receive.close()
            raise ContextError(fatal=True) from None
        finally:
            send.close()

    def poll(self):
        if self._closed:
            raise ContextError()
        try:
            if self._receive.poll():
                value = unique_json(self._receive.recv_bytes(16_384))
                self.cancel()
                if type(value) is dict and value.get('unavailable') is True:
                    raise ContextError(fatal=value.get('fatal') is True)
                return value
            if not self._process.is_alive():
                self.cancel()
                raise ContextError()
            return None
        except (OSError, EOFError, ValueError):
            self.cancel()
            raise ContextError() from None

    def cancel(self):
        if self._closed:
            return
        if self._process.is_alive():
            self._process.kill()
        self._process.join(timeout=.2)
        if self._process.is_alive():
            raise ContextError(fatal=True)
        self._process.close()
        self._receive.close()
        self._closed = True


class ContextClient:
    def __init__(self, session, *, ca_file=None):
        self._session = check_session(session)
        self._ca_file = ca_file

    def start(self, request_id, frame):
        try:
            metadata = validate_frame(frame)
            if any(metadata[k] != self._session[k] for k in ('session_id', 'source_id', 'boot_id', 'mode')):
                raise ContextError(fatal=True)
            return ProcessRequest(self._session, self._ca_file, request_id, frame)
        except ContextError:
            raise
        except Exception:
            raise ContextError() from None
