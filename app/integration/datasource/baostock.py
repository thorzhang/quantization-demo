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

from app.core.constant.stock_constant import MIN_DATE, MAX_DATE, SH_PREFIXES, SZ_PREFIXES
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
            if not bs_code:
                return []

            rs = bs.query_history_k_data_plus(
                bs_code,
                ",".join([
                    "date",
                    "open",
                    "close",
                    "high",
                    "low",
                    "preclose",
                    "volume",
                    "amount",
                    "turn",
                    "pctChg",
                    "peTTM",
                    "pbMRQ",
                    "isST",
                    "tradestatus",
                ]),
                start_date=start_date,
                end_date=end_date,
                frequency="d",
                adjustflag="2",
            )

            if rs.error_code != "0":
                raise RuntimeError(f"baostock query failed: {rs.error_msg}")

            result = []

            while rs.next():
                row = rs.get_row_data()

                # 基础字段校验（价格必须有）
                if not row or any(v == "" for v in row[:5]):
                    continue

                # --- 状态过滤 ---
                trade_status = row[13]
                if trade_status != "1":  # 跳过停牌
                    continue

                # --- 安全转换 ---
                def to_float(v):
                    return float(v) if v not in ("", None) else 0.0

                def to_int(v):
                    return int(v) if v not in ("", None) else 0

                result.append(
                    RemoteStockDailyResponse(
                        symbol=symbol,
                        date=datetime.strptime(row[0], "%Y-%m-%d").date(),
                        open=to_float(row[1]),
                        close=to_float(row[2]),
                        high=to_float(row[3]),
                        low=to_float(row[4]),
                        pre_close=to_float(row[5]),
                        volume=to_float(row[6]),
                        amount=to_float(row[7]),
                        turnover=to_float(row[8]),
                        pct_chg=to_float(row[9]),
                        pe_ttm=to_float(row[10]),
                        pb_mrq=to_float(row[11]),
                        is_st=(to_int(row[12]) == 1),
                        source=StockSource.BAOSTOCK
                    )
                )

            if not result:
                raise ValueError("empty data")

            logger.info("BaoStock拉取股票（%s）历史结束，共 %d 条", symbol, len(result))

            return result

        finally:
            bs.logout()

    @classmethod
    def _to_bs_code(cls, symbol: str) -> str:
        prefix = symbol[:1]

        if prefix in SH_PREFIXES:
            return f"sh.{symbol}"
        elif prefix in SZ_PREFIXES:
            return f"sz.{symbol}"
        else:
            return ""
