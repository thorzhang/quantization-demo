#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import logging
import time
from datetime import datetime

import baostock as bs
from func_timeout import func_timeout, FunctionTimedOut

from app.core.constant.stock_constant import (
    MIN_DATE,
    MAX_DATE,
    SH_PREFIXES,
    SZ_PREFIXES,
)
from app.core.enums.source_enum import StockSource
from app.integration.datasource.base import BaseDataSource
from app.schema.stock_daily_schema import RemoteStockDailyResponse

logger = logging.getLogger(__name__)


class BaostockSource(BaseDataSource):
    QUERY_TIMEOUT = 30
    NEXT_TIMEOUT = 20
    MAX_RETRY = 2

    def fetch_one_history(
            self,
            symbol: str,
            start_date: str = MIN_DATE,
            end_date: str = MAX_DATE
    ) -> list[RemoteStockDailyResponse]:

        last_error = None

        for attempt in range(self.MAX_RETRY + 1):

            try:
                return self._fetch_one_history_once(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date
                )

            except Exception as e:

                last_error = e

                logger.exception(
                    "BaoStock拉取失败，第 %d 次重试: %s",
                    attempt + 1,
                    symbol
                )

                # 最后一次直接抛出
                if attempt >= self.MAX_RETRY:
                    raise

                # 稍微等待一下再重试
                time.sleep(1)

        raise last_error

    def _fetch_one_history_once(
            self,
            symbol: str,
            start_date: str = MIN_DATE,
            end_date: str = MAX_DATE
    ) -> list[RemoteStockDailyResponse]:

        lg = bs.login()

        if lg.error_code != "0":
            raise RuntimeError(f"baostock login failed: {lg.error_msg}")

        try:
            bs_code = self._to_bs_code(symbol)

            if not bs_code:
                return []

            fields = ",".join([
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
            ])

            logger.info("BaoStock开始拉取股票历史: %s", symbol)

            try:
                rs = func_timeout(
                    self.QUERY_TIMEOUT,
                    bs.query_history_k_data_plus,
                    kwargs={
                        "code": bs_code,
                        "fields": fields,
                        "start_date": start_date,
                        "end_date": end_date,
                        "frequency": "d",
                        "adjustflag": "2",
                    }
                )
            except FunctionTimedOut:
                raise TimeoutError(
                    f"baostock query timeout: symbol={symbol}"
                )

            if rs.error_code != "0":
                raise RuntimeError(
                    f"baostock query failed: {rs.error_msg}"
                )

            result = []

            while True:

                try:
                    has_next = func_timeout(
                        self.NEXT_TIMEOUT,
                        self._safe_next,
                        args=(rs,)
                    )
                except FunctionTimedOut:
                    raise TimeoutError(
                        f"baostock rs.next timeout: symbol={symbol}"
                    )

                if not has_next:
                    break

                row = rs.get_row_data()

                # 基础字段校验（价格必须有）
                if not row or any(v == "" for v in row[:5]):
                    continue

                # 停牌过滤
                trade_status = row[13]

                if trade_status != "1":
                    continue

                result.append(
                    RemoteStockDailyResponse(
                        symbol=symbol,
                        date=datetime.strptime(
                            row[0],
                            "%Y-%m-%d"
                        ).date(),
                        open=self._to_float(row[1]),
                        close=self._to_float(row[2]),
                        high=self._to_float(row[3]),
                        low=self._to_float(row[4]),
                        pre_close=self._to_float(row[5]),
                        volume=self._to_float(row[6]),
                        amount=self._to_float(row[7]),
                        turnover=self._to_float(row[8]),
                        pct_chg=self._to_float(row[9]),
                        pe_ttm=self._to_float(row[10]),
                        pb_mrq=self._to_float(row[11]),
                        is_st=(self._to_int(row[12]) == 1),
                        source=StockSource.BAOSTOCK
                    )
                )

            logger.info(
                "BaoStock拉取股票（%s）历史结束，共 %d 条",
                symbol,
                len(result)
            )

            return result

        finally:
            try:
                bs.logout()
            except Exception:
                pass

    @staticmethod
    def _safe_next(rs):
        return rs.next()

    @staticmethod
    def _to_float(v):
        return float(v) if v not in ("", None) else 0.0

    @staticmethod
    def _to_int(v):
        return int(v) if v not in ("", None) else 0

    @classmethod
    def _to_bs_code(cls, symbol: str) -> str:
        prefix = symbol[:1]

        if prefix in SH_PREFIXES:
            return f"sh.{symbol}"

        elif prefix in SZ_PREFIXES:
            return f"sz.{symbol}"

        return ""
