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

from app.core.constant.stock_constant import MIN_DATE, MAX_DATE, SH_PREFIXES, SZ_PREFIXES
from app.core.enums.source_enum import StockSource
from app.integration.datasource.base import BaseDataSource
from app.schema.stock_daily_schema import RemoteStockDailyResponse

logger = logging.getLogger(__name__)


class TencentSource(BaseDataSource):

    def fetch_one_history(self, symbol: str, start_date: str = MIN_DATE, end_date: str = MAX_DATE) -> list[
        RemoteStockDailyResponse]:
        tx_code = self._to_tx_code(symbol)
        if tx_code == "":
            return []

        (processed_start_date, processed_end_date_1) = self._process_date(start_date, end_date)

        df = ak.stock_zh_a_hist_tx(symbol=tx_code, start_date=processed_start_date, end_date=processed_end_date_1)

        logger.info("tencent拉取股票（%s）历史结束", symbol)
        if df is None or df.empty:
            raise ValueError("empty data")

        return [
            RemoteStockDailyResponse(
                symbol=symbol,
                date=row["date"],
                open=row["open"],
                close=row["close"],
                high=row["high"],
                low=row["low"],
                pre_close=None,
                # 估算成交量
                volume=row["amount"] / row["close"] if row["close"] > 0 else None,
                amount=row["amount"],
                turnover=None,
                pct_chg=None,
                pe_ttm=None,
                pb_mrq=None,
                is_st=False,
                source=StockSource.TENCENT
            )
            for _, row in df.iterrows()
        ]

    def _process_date(self, start_date: str, end_date: str) -> Tuple[str, str]:
        return start_date.replace("-", ""), end_date.replace("-", "")

    @classmethod
    def _to_tx_code(cls, symbol: str) -> str:
        prefix = symbol[:1]

        if prefix in SH_PREFIXES:
            return f'sh{symbol}'
        elif prefix in SZ_PREFIXES:
            return f'sz{symbol}'
        else:
            return ""
