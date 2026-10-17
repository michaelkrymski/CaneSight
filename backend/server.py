"""Environment-configured CS-029 server factory; no default operator secret."""
import os
from .app import create_app
from .sessions import SessionManager


def create_session_app():
    token = os.environ.get('CANESIGHT_OPERATOR_TOKEN', '')
    if not token:
        raise RuntimeError('Configure CANESIGHT_OPERATOR_TOKEN before starting paired sessions')
    return create_app(session_manager=SessionManager(token))
