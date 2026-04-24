#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 数据库配置
    DATABASE_URL: str = "postgresql://postgres:postgres@10.77.70.139:5432/quantization?client_encoding=utf8"

    # Redis 配置（Celery broker）
    REDIS_URL: str = "redis://10.77.70.131:6379/7"

    # Celery 配置
    CELERY_TASK_TRACK_STARTED: bool = True
    CELERY_TASK_TIME_LIMIT: int = 3600  # 任务超时时间（秒）
    CELERY_TASK_SOFT_TIME_LIMIT: int = 3300

    # 抓取配置
    MAX_CONCURRENT_STOCKS: int = 10  # 并发数
    BATCH_SIZE: int = 50  # 批次大小
    RATE_LIMIT_SECONDS: int = 2  # 限流秒数

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
