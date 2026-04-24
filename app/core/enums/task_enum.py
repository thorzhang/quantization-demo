#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from enum import Enum


class FetchTaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    FAILED = "failed"
    DONE = "done"


class FetchProgressStatus(str, Enum):
    RETRYING = "retrying"
    RUNNING = "running"
    FAILED = "failed"
    DONE = "done"
