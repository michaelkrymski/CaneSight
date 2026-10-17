"""Environment-configured CS-029 server factory; no default operator secret."""
import os
import ipaddress
from .app import create_app
from .sessions import SessionManager


def create_session_app():
    token = os.environ.get('CANESIGHT_OPERATOR_TOKEN', '')
    if not token:
        raise RuntimeError('Configure CANESIGHT_OPERATOR_TOKEN before starting paired sessions')
    return create_app(session_manager=SessionManager(token))


def server_config(app=None, *, host='127.0.0.1', port=8000,
                  forwarded_allow_ips='127.0.0.1', ssl_keyfile=None, ssl_certfile=None):
    """Single-process launch with transport bounds before ASGI allocation.

    Proxy trust is explicit IP/CIDR configuration, never arbitrary forwarded
    headers or a wildcard. Application injection is a trusted local test seam.
    """
    import uvicorn
    try:
        proxies = [ipaddress.ip_network(value.strip(), strict=False)
                   for value in forwarded_allow_ips.split(',')]
        if not proxies or any(network.prefixlen == 0 or network.network_address.is_unspecified
                              for network in proxies):
            raise ValueError()
    except (ValueError, AttributeError):
        raise ValueError('Specify trusted proxy IPs/CIDRs, without catch-all networks') from None
    return uvicorn.Config(create_session_app if app is None else app, factory=app is None,
        host=host, port=port, workers=1, http='h11', ws='websockets', ws_max_size=8192, ws_max_queue=4,
        limit_concurrency=128, backlog=128, h11_max_incomplete_event_size=16384,
        forwarded_allow_ips=','.join(str(network) for network in proxies),
        ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile,
        access_log=False, log_config=None, log_level='warning', server_header=False)


def main():
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser(description='Bounded single-process CaneSight session server')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--forwarded-allow-ips', default='127.0.0.1',
                        help='Only reviewed proxy IPs/CIDRs, comma separated')
    args = parser.parse_args()
    try:
        config = server_config(host=args.host, port=args.port, forwarded_allow_ips=args.forwarded_allow_ips)
    except ValueError:
        parser.error('Invalid trusted proxy configuration; wildcards and catch-all networks are forbidden')
    uvicorn.Server(config).run()


if __name__ == '__main__':
    main()
