FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/app \
    APP_HOST=0.0.0.0 \
    APP_PORT=8000 \
    GUNICORN_WORKERS=2 \
    GUNICORN_TIMEOUT=120

WORKDIR ${APP_HOME}

RUN addgroup --system app && adduser --system --ingroup app app

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

RUN mkdir -p /app/logs/imports && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('APP_PORT', '8000'), timeout=3)" || exit 1

CMD ["sh", "-c", "gunicorn -k uvicorn.workers.UvicornWorker -w ${GUNICORN_WORKERS:-2} -b ${APP_HOST:-0.0.0.0}:${APP_PORT:-8000} --timeout ${GUNICORN_TIMEOUT:-120} main:app"]
