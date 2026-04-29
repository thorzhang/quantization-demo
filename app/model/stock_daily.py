#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import uuid
from datetime import date

from sqlalchemy import String, Float, Date, text, UniqueConstraint, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.model.base import Base


class StockDaily(Base):
    __tablename__ = "t_stock_daily"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuidv7()"),
        comment="主键ID（UUIDv7，时间有序）"
    )

    symbol: Mapped[str] = mapped_column(
        String(20),
        index=True,
        comment="股票代码（如 600000 / 000001）"
    )

    date: Mapped[date] = mapped_column(
        Date,
        index=True,
        comment="交易日期"
    )

    open: Mapped[float] = mapped_column(Float, comment="开盘价")
    close: Mapped[float] = mapped_column(Float, comment="收盘价")
    pre_close: Mapped[float] = mapped_column(Float, comment="昨收价")
    high: Mapped[float] = mapped_column(Float, comment="最高价")
    low: Mapped[float] = mapped_column(Float, comment="最低价")

    volume: Mapped[float] = mapped_column(Float, comment="成交量（股）")
    amount: Mapped[float] = mapped_column(Float, comment="成交额（元）")

    turnover: Mapped[float] = mapped_column(Float, comment="换手率（%）")
    pct_chg: Mapped[float] = mapped_column(Float, comment="涨跌幅（%）")

    pe_ttm: Mapped[float] = mapped_column(Float, comment="市盈率（TTM）")
    pb_mrq: Mapped[float] = mapped_column(Float, comment="市净率（MRQ）")

    trade_status: Mapped[str] = mapped_column(String(2), comment="该交易日股票是否正常交易的状态标识")
    is_st: Mapped[bool] = mapped_column(Boolean, comment="是否ST股票")

    source: Mapped[str] = mapped_column(
        String(20),
        comment="数据来源（baostock / tencent 等）"
    )

    __table_args__ = (
        UniqueConstraint('symbol', 'date', name='uq_stock_daily_symbol_date'),
    )
