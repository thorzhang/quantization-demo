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

from app.core.enums.task_enum import FetchTaskStatus


class FetchTaskRequest(BaseModel):
    resume: bool = True  # 是否断点续传


class FetchTaskCreateRequest(BaseModel):
    total_stocks: int = 0
    completed_stocks: int = 0
    failed_stocks: int = 0
    status: str = FetchTaskStatus.PENDING
    started_at: datetime = datetime.now()
    completed_at: datetime | None = None


class FetchTaskUpdateRequest(BaseModel):
    id: UUID
    total_stocks: int = 0
    completed_stocks: int = 0
    failed_stocks: int = 0
    status: str = FetchTaskStatus.PENDING
    started_at: datetime = datetime.now()
    completed_at: datetime | None = None


class FetchTaskResponse(BaseModel):
    id: UUID
    total_stocks: int = 0
    completed_stocks: int = 0
    failed_stocks: int = 0
    status: str = FetchTaskStatus.PENDING
    started_at: datetime = datetime.now()
    completed_at: datetime | None = None

    class Config:
        from_attributes = True  # 支持 ORM 对象
