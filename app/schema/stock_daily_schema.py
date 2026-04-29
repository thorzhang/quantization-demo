#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from datetime import date

from pydantic import BaseModel

from app.core.enums.source_enum import StockSource


class StockCreateRequest(BaseModel):
    symbol: str


class RemoteStockDailyResponse(BaseModel):
    symbol: str
    date: date
    open: float | None = None
    close: float | None = None
    pre_close: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None
    amount: float | None = None
    turnover: float | None = None
    pct_chg: float | None = None
    pe_ttm: float | None = None
    pb_mrq: float | None = None
    is_st: bool = False
    source: str = StockSource.BAOSTOCK

    class Config:
        from_attributes = True  # 支持 ORM 对象
