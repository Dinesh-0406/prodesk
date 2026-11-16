# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update && apt-get install -y --no-install-recommends curl tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system prodesk && useradd --system --gid prodesk --home /app prodesk

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini pyproject.toml ./
COPY migrations ./migrations
COPY app ./app
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh && mkdir -p /app/storage && chown -R prodesk:prodesk /app

USER prodesk
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD curl -fsS http://localhost:${PORT:-8000}/health || exit 1
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["api"]

# Development image with test tooling
FROM base AS dev
USER root
COPY requirements-dev.txt .
RUN pip install -r requirements-dev.txt
COPY tests ./tests
USER prodesk
