#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from datetime import date
from typing import Optional, List
from uuid import UUID

from sqlalchemy import select, update, case, func

from app.model.fetch_task import FetchTask
from app.repository.base_repository import BaseRepository


class FetchTaskRepository(BaseRepository[FetchTask]):
    model = FetchTask

    def get_fetch_task(self, task_id: UUID) -> Optional[FetchTask]:
        return self.get(task_id)

    def get_by_status_and_date_range(self, status: str, start_date: date, end_date: date) -> List[FetchTask]:
        stmt = select(self.model).where(
            self.model.status == status,
            self.model.start_date >= start_date,
            self.model.end_date <= end_date
        )
        result = self.db.execute(stmt)
        return list(result.scalars().all())

    def update_fetch_task(self, task_id: UUID, **kwargs):
        self.update_by_id(task_id, **kwargs)

    def create_fetch_task(self, fetch_task: FetchTask) -> FetchTask:
        return self.create(fetch_task)

    def increment_fetch_task(self, task_id: UUID, success: int, failed: int):
        new_total = (
                FetchTask.completed_stocks +
                FetchTask.failed_stocks +
                success +
                failed
        )

        is_done = new_total >= FetchTask.total_stocks

        stmt = (
            update(FetchTask)
            .where(FetchTask.id == task_id)
            .values(
                completed_stocks=FetchTask.completed_stocks + success,
                failed_stocks=FetchTask.failed_stocks + failed,

                status=case(
                    (
                        (FetchTask.status != 'done') & is_done,
                        'done'
                    ),
                    else_=FetchTask.status
                ),

                completed_at=case(
                    (
                        (FetchTask.status != 'done') & is_done,
                        func.now()
                    ),
                    else_=FetchTask.completed_at
                ),

                updated_at=func.now()
            )
        )

        self.db.execute(stmt)
