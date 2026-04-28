#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import logging

from celery import Celery
from celery.schedules import crontab
from kombu import Queue

from app.core.log.logger import setup_logger
from app.core.setting.config import settings

setup_logger("celery")
logger = logging.getLogger(__name__)

# 创建 Celery 应用
celery_app = Celery(
    "stock_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.task.stock_init_task"]  # 包含任务模块
)

# Celery 配置
celery_app.conf.update(
    worker_hijack_root_logger=False,
    worker_redirect_stdouts=True,
    worker_redirect_stdouts_level="INFO",

    # 任务序列化
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # 时区
    timezone="Asia/Shanghai",
    enable_utc=True,

    # 任务跟踪
    task_track_started=settings.CELERY_TASK_TRACK_STARTED,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,

    # 任务结果过期时间（秒）
    result_expires=3600,

    # 任务限流（每秒最大任务数）
    task_annotations={
        "app.task.stock_init_task.fetch_single_stock": {"rate_limit": f"{50 / settings.RATE_LIMIT_SECONDS}/s"}
    },

    # 队列配置
    task_queues=(
        Queue("stock_fetch", routing_key="stock.fetch"),
        Queue("default", routing_key="default"),
    ),
    task_default_queue="stock_fetch",
    task_default_routing_key="stock.fetch",

    # 并发配置
    worker_prefetch_multiplier=1,  # 每次只预取一个任务
    task_acks_late=True,  # 任务完成后才确认
    task_reject_on_worker_lost=True,  # worker 丢失时拒绝任务
)

# ==================== 定时任务配置 ====================
celery_app.conf.beat_schedule = {
    # 每天凌晨2点更新所有股票数据
    'update-all-stocks-daily': {
        'task': 'app.task.stock_init_task.update_all_stocks_daily',
        'schedule': crontab(hour=2, minute=0),  # 每天凌晨2点
        'args': (),
        'kwargs': {},
        'options': {
            'queue': 'stock_fetch',
            'expires': 3600,  # 1小时内未执行则过期
        }
    }
}

# 自动发现任务
celery_app.autodiscover_tasks(["app.task.stock_init_task"])

logger.info("Celery app initialized")
