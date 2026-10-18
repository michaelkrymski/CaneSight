"""Opt-in composition over exactly one accepted native backend factory.

No deployment mutation, key provisioning, alternate session authority or public
listener on import. The operator explicitly selects the currently required base.
"""
import argparse
import os

from .server import configured_service, install_context


def create_deployment_app():
    mode = os.environ.get('CANESIGHT_CONTEXT_BASE', '')
    if mode not in ('sessions', 'dashboard', 'logging'):
        raise ValueError('Explicit CANESIGHT_CONTEXT_BASE must be sessions, dashboard or logging')
    service = configured_service()
    if mode == 'sessions':
        from backend.server import create_session_app
        factory = create_session_app
    elif mode == 'dashboard':
        from backend.telemetry.live import create_dashboard_app
        factory = create_dashboard_app
    else:
        from backend.telemetry.logging_app import create_logging_app
        factory = create_logging_app
    # The base owns its manager, inference worker, auth, routes and lifespan.
    # install_context nests that lifespan and reuses app.state.sessions.
    return install_context(factory(), service)


def main(argv=None):
    import uvicorn
    from backend.server import server_config
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', choices=('127.0.0.1', '::1'), default='127.0.0.1')
    parser.add_argument('--port', type=int, default=18083)
    parser.add_argument('--forwarded-allow-ips', default='127.0.0.1')
    args = parser.parse_args(argv)
    config = server_config(app=create_deployment_app(), host=args.host, port=args.port,
                           forwarded_allow_ips=args.forwarded_allow_ips)
    uvicorn.Server(config).run()


if __name__ == '__main__':
    main()
