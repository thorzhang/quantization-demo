#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import redis

from app.core.setting.config import settings

redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
