#!/bin/bash

# 停止 Gunicorn
echo "Stopping Gunicorn..."
pkill -f "gunicorn app.main:app"

# 停止 Celery Worker
echo "Stopping Celery Worker..."
pkill -f "celery -A app.celery_app:celery_app worker"

# 停止 Celery Beat
echo "Stopping Celery Beat..."
pkill -f "celery -A app.celery_app:celery_app beat"

echo "All services stopped!"