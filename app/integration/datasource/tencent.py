#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import logging

import akshare as ak

from app.integration.datasource.base import BaseDataSource
from app.schema.stock_daily_schema import RemoteStockDailyResponse

logger = logging.getLogger(__name__)


class TencentSource(BaseDataSource):

    def fetch_one_history(self, symbol: str) -> list[RemoteStockDailyResponse]:
        tx_code = self._to_tx_code(symbol)

        df = ak.stock_zh_a_hist_tx(symbol=tx_code)

        logger.info("tencent拉取股票（s%）历史结束", symbol)
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
                # 使用成交额 / 收盘价 估算成交量（单位：股）
                volume=row["amount"] / row["close"] if row["close"] > 0 else 0,
            )
            for _, row in df.iterrows()
        ]

    @staticmethod
    def _to_tx_code(symbol: str) -> str | None:
        """
        转换为 baostock 格式：
        600000 -> sh600000
        000001 -> sz000001
        """
        # 根据股票代码添加市场前缀
        if symbol.startswith('6'):  # 上交所
            return f'sh{symbol}'
        elif symbol.startswith('0') or symbol.startswith('3'):  # 深交所
            return f'sz{symbol}'
        else:
            return None
