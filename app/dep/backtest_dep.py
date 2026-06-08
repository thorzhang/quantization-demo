#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from typing import Annotated

from fastapi import Depends

from app.dep.stock_dep import get_stock_basic_repo, get_stock_daily_repo
from app.repository.stock_basic_repository import StockBasicRepository
from app.repository.stock_daily_repository import StockDailyRepository
from app.service.signal_backtest_service import SignalBacktestService


def get_signal_backtest_service(
        stock_basic_repo: StockBasicRepository = Depends(get_stock_basic_repo),
        stock_daily_repo: StockDailyRepository = Depends(get_stock_daily_repo),
) -> SignalBacktestService:
    return SignalBacktestService(stock_basic_repo, stock_daily_repo)


SignalBacktestServiceDep = Annotated[SignalBacktestService, Depends(get_signal_backtest_service)]
