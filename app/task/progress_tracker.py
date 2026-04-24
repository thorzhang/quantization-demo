#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from typing import Dict, Any
from uuid import UUID

from app.redis.redis_client import redis_client


class ProgressTracker:
    """Redis 进度跟踪器"""

    def __init__(self):
        self.redis_client = redis_client

    def init_task(self, task_id: UUID, total: int, success: int, failed: int):
        """初始化任务"""
        self.redis_client.hset(f"task:{task_id}", mapping={
            "total": total,
            "completed": success,
            "failed": failed,
            "status": "running"
        })
        self.redis_client.expire(f"task:{task_id}", 3600)  # 1小时过期

    def update_progress(self, task_id: UUID, completed: int = None, failed: int = None):
        """更新进度"""
        pipeline = self.redis_client.pipeline()
        if completed is not None:
            pipeline.hincrby(f"task:{task_id}", "completed", completed)
        if failed is not None:
            pipeline.hincrby(f"task:{task_id}", "failed", failed)
        pipeline.execute()

    def complete_task(self, task_id: UUID, success: bool = True):
        """完成任务"""
        self.redis_client.hset(f"task:{task_id}", "status", "completed" if success else "failed")
        self.redis_client.expire(f"task:{task_id}", 300)

    def get_progress(self, task_id: UUID) -> Dict[str, Any]:
        """获取进度"""
        data = self.redis_client.hgetall(f"task:{task_id}")
        if not data:
            return None

        total = int(data.get("total", 0))
        completed = int(data.get("completed", 0))
        failed = int(data.get("failed", 0))

        return {
            "task_id": task_id,
            "total": total,
            "completed": completed,
            "failed": failed,
            "pending": total - completed - failed,
            "percentage": round((completed + failed) / total * 100, 2) if total > 0 else 0,
            "status": data.get("status", "unknown")
        }

    def delete_task(self, task_id: UUID):
        """删除任务进度"""
        self.redis_client.delete(f"task:{task_id}")


progress_tracker = ProgressTracker()
