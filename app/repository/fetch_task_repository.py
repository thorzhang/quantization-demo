#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from typing import Optional, List
from uuid import UUID

from sqlalchemy import text, select

from app.model.fetch_task import FetchTask
from app.repository.base_repository import BaseRepository


class FetchTaskRepository(BaseRepository[FetchTask]):
    model = FetchTask

    def get_fetch_task(self, task_id: UUID) -> Optional[FetchTask]:
        return self.get(task_id)

    def get_by_status(self, status: str) -> List[FetchTask]:
        stmt = select(self.model).where(self.model.status == status)
        result = self.db.execute(stmt)
        return list(result.scalars().all())

    def update_fetch_task(self, task_id: UUID, **kwargs):
        self.update_by_id(task_id, **kwargs)

    def create_fetch_task(self, fetch_task: FetchTask) -> FetchTask:
        return self.create(fetch_task)

    def increment_fetch_task(self, task_id, success, failed):
        self.db.execute(
            text("""
                 UPDATE t_fetch_task
                 SET completed_stocks = completed_stocks + :success,
                     failed_stocks    = failed_stocks + :failed,
                     status           =
                         (CASE
                              WHEN status != 'done' AND
                          completed_stocks + failed_stocks + :success + :failed >= total_stocks THEN 'done'
                              ELSE status
                         END),
                     updated_at       = NOW()
                 WHERE id = :task_id
                 """),
            {"success": success, "failed": failed, "task_id": task_id}
        )
