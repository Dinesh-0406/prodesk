#!/bin/sh
# Roles: api | worker | beat | migrate | seed | <any command>
set -e

wait_for_db() {
  python - <<'PY'
import time, sys
from sqlalchemy import create_engine, text
from app.core.config import settings
for i in range(60):
    try:
        with create_engine(settings.DATABASE_URL).connect() as c:
            c.execute(text("SELECT 1"))
        sys.exit(0)
    except Exception:
        time.sleep(1)
print("database not reachable", file=sys.stderr); sys.exit(1)
PY
}

case "$1" in
  api)
    wait_for_db
    if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then alembic upgrade head; fi
    if [ "${SEED_DEMO_DATA:-0}" = "1" ]; then python -m app.cli seed; fi
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips="*" \
      --workers "${WEB_CONCURRENCY:-2}"
    ;;
  worker)
    wait_for_db
    exec celery -A app.workers.celery_app worker --loglevel="${LOG_LEVEL:-INFO}" \
      -Q default,whatsapp,webhooks,documents --concurrency "${WORKER_CONCURRENCY:-4}"
    ;;
  beat)
    wait_for_db
    exec celery -A app.workers.celery_app beat --loglevel="${LOG_LEVEL:-INFO}" --schedule /tmp/celerybeat-schedule
    ;;
  migrate)
    wait_for_db
    exec alembic upgrade head
    ;;
  seed)
    wait_for_db
    exec python -m app.cli seed
    ;;
  *)
    exec "$@"
    ;;
esac
