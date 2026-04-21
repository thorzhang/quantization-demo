#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""

from fastapi import APIRouter

from app.api.v1.endpoint import health, user, stock

api_router = APIRouter()

# 注册子路由
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(stock.router, prefix="/stock", tags=["stock"])
