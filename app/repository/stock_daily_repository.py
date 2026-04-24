#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6
@Author : zhanglei
@File   : app.py
"""
from typing import List

from sqlalchemy.dialects.postgresql import insert

from app.model.stock_daily import StockDaily
from app.repository.base_repository import BaseRepository
from app.schema.stock_daily_schema import RemoteStockDailyResponse


class StockDailyRepository(BaseRepository[StockDaily]):
    model = StockDaily

    def bulk_upsert(self, datas: List[RemoteStockDailyResponse]) -> None:
        """高性能 bulk upsert（SQLAlchemy 2.x 推荐写法）"""
        if not datas:
            return

        values = [d.model_dump() for d in datas]

        stmt = insert(self.model)

        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "date"],
            set_={
                "open": stmt.excluded.open,
                "close": stmt.excluded.close,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "volume": stmt.excluded.volume,
            }
        )

        # 真正 bulk 执行（重点）
        self.db.execute(stmt, values)
        self.db.flush()
