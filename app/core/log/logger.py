#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import logging
import os
from logging.handlers import TimedRotatingFileHandler


def setup_logger(app_type: str):
    log_dir = "storage/log"
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, f"{app_type}.log")

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 避免重复添加 handler（非常关键）
    if logger.handlers:
        return logger

    # ===== 控制台输出 =====
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # ===== 文件输出（按天切割）=====
    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.INFO)

    # ===== 日志格式 =====
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    )

    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
