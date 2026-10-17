"""Verify the real CS-028 app's fail-closed state over loopback HTTP only."""
import argparse
import http.client
import secrets
from urllib.parse import urlsplit


def probe(base):
    origin = urlsplit(base)
    if (origin.scheme != 'http' or origin.hostname not in ('127.0.0.1', 'localhost', '::1')
            or origin.path not in ('', '/') or origin.query or origin.fragment
            or origin.username or origin.password):
        raise ValueError('Private smoke requires a loopback HTTP origin.')
    outcomes = []
    for method, path, headers, expected in [
        ('GET', '/healthz', {}, 200),
        ('GET', '/readyz', {}, 503),
        ('POST', '/v1/frames', {}, 401),
        ('POST', '/v1/frames', {'Authorization': 'Bearer invalid-' + secrets.token_hex(16)}, 401),
    ]:
        connection = http.client.HTTPConnection(origin.hostname, origin.port or 80, timeout=5)
        try:
            connection.request(method, path, body=b'' if method == 'POST' else None, headers=headers)
            with connection.getresponse() as response:
                if response.status != expected:
                    raise ValueError('Unexpected default-backend status; details suppressed.')
                outcomes.append(response.status)
        finally:
            connection.close()
    return outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='http://127.0.0.1:18000')
    args = parser.parse_args()
    try:
        probe(args.base)
    except (ValueError, OSError, http.client.HTTPException):
        print('FAIL: private backend probe; verify local target and dependency state.')
        return 1
    print('PASS: real default backend health 200; readiness 503; missing/invalid credentials 401.')
    print('Backend remains intentionally unavailable for live sensing; no model/worker enrollment claimed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
