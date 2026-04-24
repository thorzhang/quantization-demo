#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import uuid
from datetime import datetime

from sqlalchemy import String, text, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums.task_enum import FetchProgressStatus
from app.model.base import Base


class FetchProgress(Base):
    """抓取进度记录（用于断点续传）"""
    __tablename__ = "t_fetch_progress"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("uuidv7()")
    )

    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)  # Celery 任务 ID
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=FetchProgressStatus.RUNNING)
    error_msg: Mapped[str | None] = mapped_column(String(500), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 添加联合唯一索引
    __table_args__ = (
        UniqueConstraint('task_id', 'symbol', name='uq_stock_progress_task_symbol'),
    )
