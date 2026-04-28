#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from typing import List
from uuid import UUID

from sqlalchemy import select

from app.core.enums.task_enum import FetchProgressStatus
from app.model.fetch_progress import FetchProgress
from app.repository.base_repository import BaseRepository


class FetchProgressRepository(BaseRepository[FetchProgress]):
    model = FetchProgress

    def get_completed_stocks(self, task_id: UUID) -> List[str]:
        """获取已完成的股票"""
        stmt = (
            select(FetchProgress.symbol)
            .where(
                FetchProgress.task_id == task_id,
                FetchProgress.status.in_([FetchProgressStatus.DONE, FetchProgressStatus.FAILED])
            )
            .distinct()
        )

        result = self.db.execute(stmt)

        return list(result.scalars().all())

    def get_success_stocks(self, task_id: UUID) -> List[str]:
        """获取已完成的股票"""
        stmt = (
            select(FetchProgress.symbol)
            .where(
                FetchProgress.task_id == task_id,
                FetchProgress.status.in_([FetchProgressStatus.DONE])
            )
            .distinct()
        )

        result = self.db.execute(stmt)

        return list(result.scalars().all())

    def get_failed_stocks(self, task_id: UUID) -> List[str]:
        """获取已完成的股票"""
        stmt = (
            select(FetchProgress.symbol)
            .where(
                FetchProgress.task_id == task_id,
                FetchProgress.status.in_([FetchProgressStatus.FAILED])
            )
            .distinct()
        )

        result = self.db.execute(stmt)

        return list(result.scalars().all())

    def get_fetch_progress(self, task_id: UUID, symbol: str) -> FetchProgress:
        """获取某支股票的处理状态"""
        stmt = (
            select(FetchProgress)
            .where(
                FetchProgress.task_id == task_id,
                FetchProgress.symbol == symbol
            )
        )

        return self.db.execute(stmt).scalar_one_or_none()
