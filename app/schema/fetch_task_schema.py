#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from datetime import datetime, date
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.core.enums.task_enum import FetchTaskStatus


class FetchTaskCreateRequest(BaseModel):
    start_date: str
    end_date: str
    total_stocks: int = 0
    completed_stocks: int = 0
    failed_stocks: int = 0
    status: str = FetchTaskStatus.PENDING
    started_at: datetime = datetime.now()
    completed_at: datetime | None = None


class FetchTaskUpdateRequest(BaseModel):
    id: UUID
    start_date: str
    end_date: str
    total_stocks: int = 0
    completed_stocks: int = 0
    failed_stocks: int = 0
    status: str = FetchTaskStatus.PENDING
    started_at: datetime = datetime.now()
    completed_at: datetime | None = None


class FetchTaskResponse(BaseModel):
    id: UUID
    start_date: str
    end_date: str
    total_stocks: int = 0
    completed_stocks: int = 0
    failed_stocks: int = 0
    status: str = FetchTaskStatus.PENDING
    started_at: datetime = datetime.now()
    completed_at: datetime | None = None

    @field_validator('start_date', 'end_date', mode='before')
    @classmethod
    def convert_date_to_str(cls, v):
        """自动将 date 对象转为字符串"""
        if isinstance(v, date):
            return v.strftime('%Y-%m-%d')
        return v

    class Config:
        from_attributes = True  # 支持 ORM 对象
