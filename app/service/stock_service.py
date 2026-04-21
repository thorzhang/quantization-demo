#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from datetime import datetime

import akshare as ak

from app.model.stock import StockDaily
from app.repository.stock_repository import StockRepository


class StockService:

    def __init__(self, db):
        self.repo = StockRepository(db)

    def fetch_and_store(self, symbol: str):
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily")

        data_list = []

        for _, row in df.iterrows():
            stock = StockDaily(
                symbol=symbol,
                date=datetime.strptime(row["日期"], "%Y-%m-%d").date(),
                open=row["开盘"],
                close=row["收盘"],
                high=row["最高"],
                low=row["最低"],
                volume=row["成交量"],
            )
            data_list.append(stock)

        self.repo.bulk_insert(data_list)
