#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from datetime import date

from pydantic import BaseModel


class StockCreateRequest(BaseModel):
    symbol: str


class RemoteStockDailyResponse(BaseModel):
    symbol: str
    date: date
    open: float
    close: float
    high: float
    low: float
    volume: float
    source: str

    class Config:
        from_attributes = True  # 支持 ORM 对象
