"""Serve the CS-041 fixture dashboard on loopback only, without dependencies."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2] / 'dashboard'
ASSETS = {
    '/': ('index.html', 'text/html; charset=utf-8'),
    '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
    '/model.js': ('model.js', 'text/javascript; charset=utf-8'),
    '/style.css': ('style.css', 'text/css; charset=utf-8'),
    '/icon.svg': ('icon.svg', 'image/svg+xml'),
}
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
       "connect-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = 'CaneSightFixture'
    sys_version = ''

    def log_message(self, *_args):
        pass  # Do not log URLs or request headers.

    def respond(self, status, content=b'', content_type='text/plain; charset=utf-8'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', CSP)
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(content)

    def do_GET(self):
        host = self.headers.get('Host', '')
        if host not in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'):
            return self.respond(403)
        target = urlsplit(self.path)
        if target.query or target.fragment or target.scheme or target.netloc:
            return self.respond(400)
        asset = ASSETS.get(target.path)
        if asset is None:
            return self.respond(404)
        filename, kind = asset
        self.respond(200, (ROOT / filename).read_bytes(), kind)

    do_HEAD = do_GET

    def do_POST(self):
        self.respond(405)

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_POST


def create_server(port=8041):
    return ThreadingHTTPServer(('127.0.0.1', port), DashboardHandler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8041)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Choose a port between 1 and 65535')
    with create_server(args.port) as server:
        print(f'Fixture dashboard: http://127.0.0.1:{server.server_port}', flush=True)
        print('Synthetic replay only; no production connection or credentials.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
