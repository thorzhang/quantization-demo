#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.core.enums.task_enum import FetchProgressStatus


class FetchProgressCreateRequest(BaseModel):
    task_id: UUID
    symbol: str
    status: str = FetchProgressStatus.PENDING
    error_msg: str = None
    completed_at: datetime | None = None


class FetchProgressUpdateRequest(BaseModel):
    id: UUID
    task_id: UUID
    symbol: str
    status: str = FetchProgressStatus.PENDING
    error_msg: str = None
    completed_at: datetime | None = None


class FetchProgressResponse(BaseModel):
    id: UUID
    task_id: UUID
    symbol: str
    status: str
    error_msg: str | None = None
    completed_at: datetime | None = None

    class Config:
        from_attributes = True  # 支持 ORM 对象
