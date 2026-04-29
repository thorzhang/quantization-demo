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
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date
        )

        logger.info("eastmoney拉取股票（%s）历史结束", symbol)

        if df is None or df.empty:
            raise ValueError("empty data")

        # =====================================================
        # 1️⃣ 先 copy（数据隔离，避免 view / chained issue）
        # =====================================================
        df = df.copy()

        # =====================================================
        # 2️⃣ 再 rename（统一 schema）
        # =====================================================
        df = df.rename(columns={
            "日期": "date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "volume",
            "成交额": "amount"
        })

        # =====================================================
        # 3️⃣ 成交量统一（手 → 股）
        # =====================================================
        df["volume"] = df["volume"] * 100

        # =====================================================
        # 4️⃣ 衍生字段（行情计算）
        # =====================================================
        df["pre_close"] = df["close"].shift(1)

        df["pct_chg"] = (
                (df["close"] - df["pre_close"]) / df["pre_close"] * 100
        )

        # =====================================================
        # 5️⃣ Baostock 对齐缺失字段
        # =====================================================
        df["pe_ttm"] = None
        df["pb_mrq"] = None
        df["is_st"] = False

        # =====================================================
        # 6️⃣ 转换为统一模型
        # =====================================================
        return [
            RemoteStockDailyResponse(
                symbol=symbol,
                date=row["date"],
                open=row["open"],
                close=row["close"],
                high=row["high"],
                low=row["low"],
                pre_close=row["pre_close"],
                volume=row["volume"],
                amount=row["amount"],
                turnover=row.get("换手率"),
                pct_chg=row["pct_chg"],
                pe_ttm=None,
                pb_mrq=None,
                is_st=False,
                source=StockSource.EASTMONEY
            )
            for _, row in df.iterrows()
        ]

    def _process_date(self, start_date: str, end_date: str) -> Tuple[str, str]:
        return start_date.replace("-", ""), end_date.replace("-", "")
