#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import logging
from typing import Tuple

import akshare as ak

from app.core.constant.stock_constant import MIN_DATE, MAX_DATE
from app.core.enums.source_enum import StockSource
from app.integration.datasource.base import BaseDataSource
from app.schema.stock_daily_schema import RemoteStockDailyResponse

logger = logging.getLogger(__name__)


class EastMoneySource(BaseDataSource):

    def fetch_one_history(self, symbol: str, start_date: str = MIN_DATE, end_date: str = MAX_DATE) -> list[
        RemoteStockDailyResponse]:
        df = ak.stock_zh_a_hist(symbol=symbol, start_date=start_date, end_date=end_date)

        logger.info("eastmoney拉取股票（%s）历史结束", symbol)

        if df is None:
            raise ValueError("empty data")

        return [
            RemoteStockDailyResponse(
                symbol=symbol,
                date=row["日期"],
                open=row["开盘"],
                close=row["收盘"],
                high=row["最高"],
                low=row["最低"],
                volume=row["成交量"],
                source=StockSource.EASTMONEY
            )
            for _, row in df.iterrows()
        ]

    def _process_date(self, start_date: str, end_date: str) -> Tuple[str, str]:
        return start_date.replace("-", ""), end_date.replace("-", "")
