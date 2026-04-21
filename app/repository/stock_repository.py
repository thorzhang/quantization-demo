#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.model.stock import StockDaily


class StockRepository:

    def __init__(self, db: Session):
        self.db = db

    def bulk_insert(self, data_list):
        self.db.add_all(data_list)
        self.db.commit()

    def get_by_symbol(self, symbol: str):
        stmt = (
            select(StockDaily)
            .where(StockDaily.symbol == symbol)
            .order_by(StockDaily.date)
        )
        return self.db.execute(stmt).scalars().all()
