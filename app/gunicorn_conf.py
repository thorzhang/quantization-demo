#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from app.core.log.logging import init_logging

# 设置超时时间为 0，禁用超时限制
timeout = 21600

# 优雅超时保留默认或适当设置
graceful_timeout = 10800


def on_starting(server):
    # master 进程
    init_logging("app")


def post_fork(server, worker):
    # 每个 worker 进程重新初始化
    init_logging("app")
