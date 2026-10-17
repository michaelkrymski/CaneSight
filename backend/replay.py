"""Explicit software-only upload target. It never reports model readiness."""
import os
import time
from .app import FrameIngress, SourceGrant, create_app


def create_replay_app():
    token = os.environ.get('CANESIGHT_REPLAY_TOKEN', '')
    grant = SourceGrant(token, 'demo-session', 'pi-camera-1', 'pi-boot-1',
                        'replay', time.monotonic() + 300)
    return create_app(ingress=FrameIngress([grant]))
