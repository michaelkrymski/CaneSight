"""Container-local readiness check. Does not log response bodies or errors."""
import http.client
import os


def ready():
    try:
        port = int(os.environ.get('CANESIGHT_INTERNAL_PORT', '8000'))
        if not 1 <= port <= 65535:
            return False
    except ValueError:
        return False
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
    try:
        connection.request('GET', '/readyz')
        return connection.getresponse().status == 200
    except (OSError, http.client.HTTPException):
        return False
    finally:
        connection.close()


if __name__ == '__main__':
    raise SystemExit(0 if ready() else 1)
