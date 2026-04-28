#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import logging
from datetime import datetime

import baostock as bs

from app.core.constant.stock_constant import MIN_DATE, MAX_DATE
from app.core.enums.source_enum import StockSource
from app.integration.datasource.base import BaseDataSource
from app.schema.stock_daily_schema import RemoteStockDailyResponse

logger = logging.getLogger(__name__)


class BaostockSource(BaseDataSource):

    def fetch_one_history(self, symbol: str, start_date: str = MIN_DATE, end_date: str = MAX_DATE) -> list[
        RemoteStockDailyResponse]:
        lg = bs.login()
        if lg.error_code != "0":
            raise RuntimeError(f"baostock login failed: {lg.error_msg}")

        try:
            bs_code = self._to_bs_code(symbol)

            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,open,high,low,close,volume",
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="2",  # 前复权
            )

            logger.info("BaoStock拉取股票（%s）历史结束", symbol)

            if rs.error_code != "0":
                raise RuntimeError(f"baostock query failed: {rs.error_msg}")

            result = []

            while rs.next():
                row = rs.get_row_data()

                # 过滤空数据
                if not row or any(v == "" for v in row[:6]):
                    continue

                result.append(
                    RemoteStockDailyResponse(
                        symbol=symbol,
                        date=datetime.strptime(row[0], "%Y-%m-%d").date(),
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume=float(row[5]),
                        source=StockSource.BAOSTOCK
                    )
                )

            if not result:
                raise ValueError("empty data")

            return result

        finally:
            bs.logout()

    @classmethod
    def _to_bs_code(cls, symbol: str) -> str:
        """
        转换为 baostock 格式：
        600000 -> sh.600000
        000001 -> sz.000001
        """
        if symbol.startswith("6"):
            return f"sh.{symbol}"
        else:
            return f"sz.{symbol}"
