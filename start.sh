#!/bin/bash

# ==============================
# 基础路径（非常关键）
# ==============================
BASE_DIR=$(cd "$(dirname "$0")"; pwd)
cd $BASE_DIR

LOG_DIR=$BASE_DIR/storage/log
mkdir -p $LOG_DIR

echo "======================================"
echo "Base Dir : $BASE_DIR"
echo "Log Dir  : $LOG_DIR"
echo "Starting services..."
echo "======================================"

# ==============================
# App (Gunicorn)
# ==============================
nohup uv run gunicorn app.main:app \
-k uvicorn.workers.UvicornWorker \
-w 2 \
-b 0.0.0.0:8000 \
--timeout 60 \
-c app/gunicorn_conf.py \
> $LOG_DIR/app.out 2>&1 &

echo "app started"

# ==============================
# Celery Worker
# ==============================
nohup env SERVICE_NAME=celery_worker \
uv run celery -A app.celery_app:celery_app worker \
-l info -c 2 \
> $LOG_DIR/celery_worker.out 2>&1 &

echo "Celery Worker started"

# ==============================
# Celery Beat
# ==============================
nohup env SERVICE_NAME=celery_beat \
uv run celery -A app.celery_app:celery_app beat \
-l info \
> $LOG_DIR/celery_beat.out 2>&1 &

echo "Celery Beat started"

echo "======================================"
echo "All services started successfully!"
echo "Logs: $LOG_DIR"
echo "======================================"
