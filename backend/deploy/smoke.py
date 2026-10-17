"""TLS and authentication handshake probes; no images or movement commands sent.

Reads CS_SMOKE_BASE_URL, CS_SMOKE_WS_PATH and CS_SMOKE_TOKEN from the environment.
Bearer-header authentication must match the accepted CS-029 contract before use.
"""
import base64
import hashlib
import http.client
import os
import secrets
import socket
import ssl
from urllib.parse import urlsplit


class ProbeError(Exception):
    pass


def target(base_url):
    parsed = urlsplit(base_url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ProbeError('Use an HTTPS origin without credentials, query or path.')
    try:
        port = parsed.port or 443
    except ValueError:
        raise ProbeError('Invalid HTTPS port.') from None
    return parsed.hostname, port


def https_status(host, port, path, context):
    connection = http.client.HTTPSConnection(host, port, context=context, timeout=5)
    try:
        connection.request('GET', path)
        with connection.getresponse() as response:
            if response.status != 200:
                raise ProbeError(path + ' did not return HTTP 200.')
    finally:
        connection.close()


def ws_status(host, port, path, token, context):
    key = base64.b64encode(secrets.token_bytes(16)).decode('ascii')
    hostname = '[' + host + ']' if ':' in host else host
    authority = hostname if port == 443 else f'{hostname}:{port}'
    headers = [f'GET {path} HTTP/1.1', f'Host: {authority}', 'Upgrade: websocket',
               'Connection: Upgrade', f'Sec-WebSocket-Key: {key}', 'Sec-WebSocket-Version: 13']
    if token is not None:
        headers.append('Authorization: Bearer ' + token)
    with socket.create_connection((host, port), timeout=5) as raw:
        with context.wrap_socket(raw, server_hostname=host) as connection:
            connection.sendall(('\r\n'.join(headers) + '\r\n\r\n').encode('ascii'))
            # Parse only bounded HTTP upgrade headers. Never read or print scene data.
            response = http.client.HTTPResponse(connection)
            response.begin()
            status = response.status
            if status == 101:
                expected = base64.b64encode(hashlib.sha1(
                    (key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode('ascii')).digest()).decode('ascii')
                if (response.getheader('Sec-WebSocket-Accept') != expected
                        or response.getheader('Upgrade', '').lower() != 'websocket'
                        or 'upgrade' not in [v.strip().lower() for v in response.getheader('Connection', '').split(',')]):
                    raise ProbeError('Invalid WebSocket upgrade response.')
                # A masked, empty close frame ends this probe without application messages.
                connection.sendall(b'\x88\x80' + secrets.token_bytes(4))
            return status


def run(base_url, ws_path, token, context=None):
    host, port = target(base_url)
    path = urlsplit(ws_path)
    if (path.scheme or path.netloc or not ws_path.startswith('/v1/')
            or path.fragment or any(ord(c) < 33 or ord(c) > 126 for c in ws_path)):
        raise ProbeError('Use an ASCII /v1/ WebSocket path with no whitespace or fragment.')
    if not token or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ProbeError('CS_SMOKE_TOKEN must contain a nonempty ASCII bearer credential.')
    context = context or ssl.create_default_context()
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise ProbeError('Certificate and hostname verification are required.')
    https_status(host, port, '/healthz', context)
    https_status(host, port, '/readyz', context)
    for credential in (None, 'invalid-' + secrets.token_hex(16)):
        if ws_status(host, port, ws_path, credential, context) not in (401, 403):
            raise ProbeError('Unauthenticated or invalid-token WebSocket handshake was not rejected.')
    if ws_status(host, port, ws_path, token, context) != 101:
        raise ProbeError('Authenticated WebSocket upgrade failed.')


def main():
    try:
        run(os.environ.get('CS_SMOKE_BASE_URL', ''), os.environ.get('CS_SMOKE_WS_PATH', ''),
            os.environ.get('CS_SMOKE_TOKEN', ''))
    except (ProbeError, OSError, ValueError, http.client.HTTPException):
        # Library exceptions can contain URLs, headers or response bodies.
        print('Deployment probe failed. Check configuration, TLS, readiness and CS-029 authentication locally; details suppressed.')
        return 1
    print('PASS: HTTPS health/readiness; WSS rejects missing/invalid tokens and accepts the configured token.')
    print('Handshake checks only; session isolation, observations and physical devices are not verified.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
