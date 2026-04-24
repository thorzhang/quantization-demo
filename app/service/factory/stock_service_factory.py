#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from app.repository.fetch_progress_repository import FetchProgressRepository
from app.repository.fetch_task_repository import FetchTaskRepository
from app.repository.stock_basic_repository import StockBasicRepository
from app.repository.stock_daily_repository import StockDailyRepository
from app.service.stock_service import StockService


def create_stock_service(db):
    return StockService(
        StockBasicRepository(db),
        StockDailyRepository(db),
        FetchTaskRepository(db),
        FetchProgressRepository(db),
    )
