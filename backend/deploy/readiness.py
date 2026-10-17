"""Container-local readiness check. Does not log response bodies or errors."""
import http.client


def ready():
    connection = http.client.HTTPConnection('127.0.0.1', 8000, timeout=3)
    try:
        connection.request('GET', '/readyz')
        return connection.getresponse().status == 200
    except (OSError, http.client.HTTPException):
        return False
    finally:
        connection.close()


if __name__ == '__main__':
    raise SystemExit(0 if ready() else 1)
