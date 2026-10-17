"""Verify health-only HTTPS without credentials or TLS verification bypass."""
import argparse
import http.client
import ssl

from backend.deploy.smoke import ProbeError, target


def run(base, context=None):
    host, port = target(base)
    context = context or ssl.create_default_context()
    if not context.check_hostname or context.verify_mode != ssl.CERT_REQUIRED:
        raise ProbeError('Certificate and hostname verification are required.')
    expiry = None
    for method, path, expected in (('GET', '/healthz', 200), ('GET', '/readyz', 503),
                                   ('GET', '/', 503), ('POST', '/v1/sessions', 503),
                                   ('POST', '/v1/frames', 503), ('GET', '/v1/events', 503)):
        connection = http.client.HTTPSConnection(host, port, timeout=5, context=context)
        try:
            connection.connect()
            expiry = connection.sock.getpeercert()['notAfter']
            headers = {'Connection': 'Upgrade', 'Upgrade': 'websocket'} if path == '/v1/events' else {}
            connection.request(method, path, headers=headers)
            response = connection.getresponse()
            if response.status != expected or response.getheader('Cache-Control') != 'no-store':
                raise ProbeError('Unexpected bootstrap route or cache behavior.')
            if len(response.read(8193)) > 8192:
                raise ProbeError('Unexpected oversized bootstrap response.')
        finally:
            connection.close()
    return expiry


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', required=True, help='HTTPS origin, without path or credentials')
    args = parser.parse_args()
    try:
        expiry = run(args.base)
    except (ProbeError, OSError, ValueError, KeyError, http.client.HTTPException):
        print('Bootstrap probe failed; check TLS, health and closed API routes locally.')
        raise SystemExit(1)
    print('PASS: verified HTTPS; health 200; readiness and API routes 503 (application unavailable).')
    print('Certificate expires:', expiry)
