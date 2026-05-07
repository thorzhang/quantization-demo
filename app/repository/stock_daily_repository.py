#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6
@Author : zhanglei
@File   : app.py
"""
from collections import defaultdict
from typing import List, Dict

from sqlalchemy import func, select
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
                "pre_close": stmt.excluded.pre_close,
                "high": stmt.excluded.high,
                "low": stmt.excluded.low,
                "volume": stmt.excluded.volume,
                "amount": stmt.excluded.amount,
                "turnover": stmt.excluded.turnover,
                "pct_chg": stmt.excluded.pct_chg,
                "pe_ttm": stmt.excluded.pe_ttm,
                "pb_mrq": stmt.excluded.pb_mrq,
                "is_st": stmt.excluded.is_st,
                "source": stmt.excluded.source,
                "updated_at": func.now()
            }
        )

        # 真正 bulk 执行（重点）
        self.db.execute(stmt, values)
        self.db.flush()

    def get_all_recent_kline(self, limit: int) -> Dict[str, List[StockDaily]]:
        subquery = (
            select(
                StockDaily.id,
                func.row_number().over(
                    partition_by=StockDaily.symbol,
                    order_by=StockDaily.date.desc()
                ).label("rn")
            ).select_from(StockDaily)
        ).subquery()

        stmt = (
            select(StockDaily)
            .join(subquery, StockDaily.id == subquery.c.id)
            .where(subquery.c.rn <= limit)
            .order_by(StockDaily.symbol, StockDaily.date.asc())
        )

        rows = self.db.execute(stmt).scalars().all()

        grouped: Dict[str, List[StockDaily]] = defaultdict(list)

        for obj in rows:
            grouped[obj.symbol].append(obj)

        return grouped
