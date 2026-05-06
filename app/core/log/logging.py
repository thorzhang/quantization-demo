#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import logging
import logging.config
import os


def build_log_config(service_name: str):
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    log_dir = os.path.join(base_dir, "storage", "log")
    os.makedirs(log_dir, exist_ok=True)

    return {
        "version": 1,
        "disable_existing_loggers": False,

        "formatters": {
            "default": {
                "format": "%(asctime)s | %(levelname)s | %(processName)s | %(name)s | %(message)s",
            },
        },

        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            },
            "file": {
                "class": "concurrent_log_handler.ConcurrentRotatingFileHandler",
                "filename": f"{log_dir}/{service_name}.log",
                "maxBytes": 100 * 1024 * 1024,
                "backupCount": 7,
                "encoding": "utf-8",
                "formatter": "default",
            },
        },

        "loggers": {
            # 你的业务日志
            "app": {
                "handlers": ["console", "file"],
                "level": "INFO",
                "propagate": False,
            },

            # SQLAlchemy 降噪
            "sqlalchemy.engine": {
                "level": "WARNING",
            },

            # Celery
            "celery": {
                "level": "INFO",
            },

            # uvicorn（避免重复日志）
            "uvicorn": {
                "handlers": ["console"],
                "level": "INFO",
                "propagate": False,
            },
        },

        "root": {
            "handlers": ["console"],
            "level": "INFO",
        },
    }


def init_logging(service_name: str):
    root_logger = logging.getLogger()
    # 如果已经有 handler，就不要重复初始化
    if root_logger.handlers:
        return

    config = build_log_config(service_name)
    logging.config.dictConfig(config)
