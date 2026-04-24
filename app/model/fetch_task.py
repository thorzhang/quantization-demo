#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import uuid
from datetime import datetime

from sqlalchemy import String, text, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums.task_enum import FetchTaskStatus
from app.model.base import Base


class FetchTask(Base):
    """抓取任务记录"""
    __tablename__ = "t_fetch_task"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuidv7()")
    )

    total_stocks: Mapped[int] = mapped_column(Integer, default=0)
    completed_stocks: Mapped[int] = mapped_column(Integer, default=0)
    failed_stocks: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=FetchTaskStatus.PENDING)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
