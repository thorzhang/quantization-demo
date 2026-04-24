#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from abc import ABC, abstractmethod

from app.schema.stock_daily_schema import RemoteStockDailyResponse


class BaseDataSource(ABC):

    @abstractmethod
    def fetch_one_history(self, symbol: str) -> list[RemoteStockDailyResponse]:
        pass
