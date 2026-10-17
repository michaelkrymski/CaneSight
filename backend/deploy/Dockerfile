# Build from repository root. Supply a reviewed immutable Python image reference.
ARG PYTHON_IMAGE=python@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
FROM ${PYTHON_IMAGE}
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /opt/canesight
COPY backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements.txt
# Explicit allowlist: never copy a checkout's .env, keys, logs or scene images.
COPY shared/protocol/v1/ /opt/canesight/shared/protocol/v1/
COPY backend/__init__.py backend/app.py backend/replay.py backend/limits.py backend/server.py backend/sessions.py backend/inference_worker.py backend/freshness.py backend/events_client.py /opt/canesight/backend/
COPY backend/deploy/readiness.py /opt/canesight/readiness.py
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=4s --start-period=60s --retries=3 CMD ["python", "/opt/canesight/readiness.py"]
CMD ["python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
