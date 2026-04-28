#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from abc import ABC, abstractmethod
from typing import Tuple

from app.core.constant.stock_constant import MIN_DATE, MAX_DATE
from app.schema.stock_daily_schema import RemoteStockDailyResponse


class BaseDataSource(ABC):

    @abstractmethod
    def fetch_one_history(self, symbol: str, start_date: str = MIN_DATE, end_date: str = MAX_DATE) -> list[
        RemoteStockDailyResponse]:
        pass

    def _process_date(self, start_date: str, end_date: str) -> Tuple[str, str]:
        return start_date, end_date
