#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from sqlalchemy import select

from app.model.stock_basic import StockBasic

# !/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from typing import List, Dict

from app.repository.base_repository import BaseRepository


class StockBasicRepository(BaseRepository[StockBasic]):
    model = StockBasic

    def save_all(self, stock_basics: List[StockBasic]):
        self.db.add_all(stock_basics)
        self.db.flush()

    def list_symbols(self) -> list[str]:
        stmt = select(StockBasic.symbol)
        return list(self.db.execute(stmt).scalars().all())[:1]

    def save_all_stocks(self, stocks: List[Dict[str, str]]):
        """批量保存股票列表"""
        # 取出已有 symbol
        stmt = select(StockBasic.symbol)
        existing_symbols = set(self.db.execute(stmt).scalars().all())

        # 过滤掉已存在的
        new_objs = [
            StockBasic(**stock)
            for stock in stocks
            if stock["symbol"] not in existing_symbols
        ]

        # 批量插入
        if new_objs:
            self.db.add_all(new_objs)

        self.db.flush()
