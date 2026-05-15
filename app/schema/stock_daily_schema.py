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


class StockRecommendRequest(BaseModel):
    strategy_name: str = "conservative_trend"


class StockBackTestRequest(BaseModel):
    strategy_name: str = "robust_trend"
    start_date: str
    end_date: str
    top_k: int = 10
    min_history: int = 120
    take_profit: float = 0.20
    stop_loss: float = -0.10
    min_hold_days: int = 5
    max_hold_days: int = 60
    init_position_pct: float = 0.05
    max_single_position_pct: float = 0.15
    max_total_positions: int = 15
    score_threshold: int = 70
    market_width_sample_size: int = 500
    market_width_frequency: int = 5


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
