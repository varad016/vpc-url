# Pin to an exact patch tag from Docker Hub once you pick one (e.g. 3.12.x-slim-bookworm)
FROM python:3.12-slim-bookworm

# Logs go straight to stdout (visible in kubectl logs), no .pyc clutter
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dependencies first so this layer is cached when only code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Numeric UID so Kubernetes can verify runAsNonRoot
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser

COPY --chown=10001:10001 . .

USER 10001

EXPOSE 5000

# One worker + threads: metrics stay accurate, and you scale with replicas (HPA)
ENV WEB_CONCURRENCY=1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--threads", "4", "--access-logfile", "-", "main:app"]
