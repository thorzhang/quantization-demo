#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from app.core.log.logging import init_logging


def on_starting(server):
    # master 进程
    init_logging("app")


def post_fork(server, worker):
    # 每个 worker 进程重新初始化
    init_logging("app")
