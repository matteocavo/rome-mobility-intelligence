FROM python:3.12-slim-bookworm@sha256:6dd8b6dab6b3adc7812bab69eca5dbdc1a5cc690ad28306d234ffb4ef8ac9753 AS builder
COPY requirements-runtime.txt /tmp/requirements-runtime.txt
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir --only-binary=:all: -r /tmp/requirements-runtime.txt

FROM python:3.12-slim-bookworm@sha256:6dd8b6dab6b3adc7812bab69eca5dbdc1a5cc690ad28306d234ffb4ef8ac9753
ENV PATH="/opt/venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ENVIRONMENT=production
RUN groupadd --gid 10001 rmi && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin rmi
WORKDIR /srv/app
COPY --from=builder /opt/venv /opt/venv
COPY app ./app
COPY scripts/__init__.py scripts/serve.py scripts/healthcheck.py ./scripts/
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s CMD ["python", "-m", "scripts.healthcheck"]
CMD ["python", "-m", "scripts.serve", "--host", "0.0.0.0", "--port", "8000"]
