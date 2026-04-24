#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import logging

import akshare as ak

from app.integration.datasource.base import BaseDataSource
from app.schema.stock_daily_schema import RemoteStockDailyResponse

logger = logging.getLogger(__name__)


class EastMoneySource(BaseDataSource):

    def fetch_one_history(self, symbol: str) -> list[RemoteStockDailyResponse]:
        df = ak.stock_zh_a_hist(symbol=symbol)

        logger.info("eastmoney拉取股票（s%）历史结束", symbol)

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
            )
            for _, row in df.iterrows()
        ]
