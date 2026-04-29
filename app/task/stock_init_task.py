#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import logging
# !/usr/bin/env python
# -*- coding: utf-8 -*-
import time
import uuid
from datetime import datetime, timedelta
from typing import List
from uuid import UUID

from celery import chord

from app.celery_app import celery_app
from app.core.enums.task_enum import FetchTaskStatus, FetchProgressStatus
from app.db.database import SessionLocal
from app.db.uow import UnitOfWork
from app.model.fetch_progress import FetchProgress
from app.model.fetch_task import FetchTask
from app.schema.fetch_progress_schema import FetchProgressCreateRequest
from app.task.progress_tracker import progress_tracker

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.task.stock_init_task.fetch_all_stocks")
def fetch_all_stocks(self, task_id: UUID, resume: bool = True) -> dict:
    logger.info("celery task: fetch_all_stocks任务启动")

    from app.service.factory.stock_service_factory import create_stock_service

    with UnitOfWork() as uow:
        stock_service = create_stock_service(uow.db)
        total = len(stock_service.get_all_symbols())
        success_num = 0
        failed_num = 0

        if resume:
            success_num = len(stock_service.get_success_stocks(task_id))
            failed_num = len(stock_service.get_failed_stocks(task_id))

        stock_service.update_fetch_task_by_id(
            task_id,
            total_stocks=total,
            completed_stocks=success_num,
            failed_stocks=failed_num,
            status=FetchTaskStatus.RUNNING
        )

        progress_tracker.init_task(task_id, total, success_num, failed_num)
        pending_symbols = stock_service.get_pending_stocks(task_id)

    try:
        batch_size = 50

        for i in range(0, len(pending_symbols), batch_size):
            batch_id = str(uuid.uuid4())

            batch = pending_symbols[i:i + batch_size]

            header = [
                fetch_single_stock.s(symbol, task_id)
                for symbol in batch
            ]

            callback = on_batch_complete.s(task_id, batch_id)

            chord(header)(callback)

            logger.info("celery task: fetch_all_stocks启动，task_id=%s, batch_id=%s，batch[0]=%s",
                        task_id, batch_id, batch[0])

            if i + batch_size < len(pending_symbols):
                time.sleep(2)

        return {"status": "dispatched", "total": total}

    except Exception:
        with UnitOfWork() as uow:
            stock_service = create_stock_service(uow.db)
            progress_tracker.complete_task(task_id, success=False)
            stock_service.update_fetch_task_by_id(
                task_id,
                status=FetchTaskStatus.FAILED,
                completed_at=datetime.now()
            )
        raise


@celery_app.task(
    bind=True,
    name="app.task.stock_init_task.fetch_single_stock",
    max_retries=3,
    default_retry_delay=60
)
def fetch_single_stock(self, symbol: str, task_id: str) -> dict:
    from app.service.factory.stock_service_factory import create_stock_service

    logger.info("celery task: fetch_single_stock启动，task_id=%s，symbol=%s", task_id, symbol)

    # =========================
    # 1️⃣ 短事务：初始化 / 幂等控制
    # =========================
    with UnitOfWork() as uow:
        stock_service = create_stock_service(uow.db)

        progress = stock_service.get_fetch_progress(task_id, symbol)

        # 已完成 → 幂等返回
        if progress and progress.status == "success":
            return {"status": "already_completed"}

        # 不存在 → 创建
        if not progress:
            stock_service.create_fetch_progress(
                FetchProgressCreateRequest(
                    task_id=task_id,
                    symbol=symbol,
                    status=FetchProgressStatus.RUNNING
                )
            )
        else:
            # 存在但不是成功 → 重置为 running（用于 retry 场景）
            stock_service.update_fetch_progress_by_id(
                progress.id,
                status=FetchProgressStatus.RUNNING
            )

        fetch_task = stock_service.get_fetch_task(task_id)

    # =========================
    # 2️⃣ 无事务：外部IO（避免长事务）
    # =========================
    try:
        stock_datas = stock_service.fetch_one_history(symbol, fetch_task.start_date, fetch_task.end_date)

    except Exception as e:
        # =========================
        # 3️⃣ retry 前保证状态一致
        # =========================
        with UnitOfWork() as uow:
            stock_service = create_stock_service(uow.db)

            progress = stock_service.get_fetch_progress(task_id, symbol)

            if progress:
                stock_service.update_fetch_progress_by_id(
                    progress.id,
                    status=FetchProgressStatus.RETRYING
                )

        raise self.retry(exc=e)

    # =========================
    # 4️⃣ 短事务：写入结果
    # =========================
    with UnitOfWork() as uow:
        stock_service = create_stock_service(uow.db)

        progress = stock_service.get_fetch_progress(task_id, symbol)

        # 再次幂等保护（防并发 / 重试）
        if progress and progress.status == "success":
            return {"status": "already_completed"}

        stock_service.bulk_upsert_stock_daily(stock_datas)

        stock_service.update_fetch_progress_by_id(
            progress.id,
            status=FetchProgressStatus.DONE,
            completed_at=datetime.now()
        )

        logger.info("celery task: fetch_single_stock结束，task_id=%s, symbol=%s",
                    task_id, symbol)

    return {"status": "success"}


@celery_app.task(name="app.task.stock_init_task.on_batch_complete")
def on_batch_complete(results: List[dict], task_id: UUID, batch_id: str):
    from app.service.factory.stock_service_factory import create_stock_service
    from app.redis.redis_client import redis_client

    logger.info("celery task: on_batch_complete启动，task_id=%s, results=%s",
                task_id, results)

    key = f"task:{task_id}:batch:{batch_id}"

    # =========================
    # 1 尝试抢占执行权
    # =========================
    # 只有不存在时才设置为 processing
    if not redis_client.set(key, "processing", nx=True, ex=86400):
        status = redis_client.get(key)

        if status == b"done":
            return {"status": "duplicate_skipped"}

        # 如果是 processing，说明可能是上一次执行挂了
        # 👉 可以选择继续执行（恢复能力）
        # 这里我们允许继续执行
    try:
        # =========================
        # 2 正常业务逻辑
        # =========================
        success_count = sum(1 for r in results if r.get("status") == "success")
        failed_count = sum(1 for r in results if r.get("status") != "success")

        # Redis 进度
        try:
            progress_tracker.update_progress(task_id, success_count, failed_count)
        except Exception:
            pass

        # DB 更新（原子）
        with UnitOfWork() as uow:
            stock_service = create_stock_service(uow.db)

            stock_service.increment_fetch_task(
                task_id,
                success_count,
                failed_count
            )

        # =========================
        # 3 标记完成（关键）
        # =========================
        redis_client.set(key, "done", ex=86400)

        logger.info("celery task: on_batch_complete结束，task_id=%s, results=%s",
                    task_id, results)
        return {"success": success_count, "failed": failed_count}

    except Exception as e:
        # =========================
        # 4 失败恢复机制（关键）
        # =========================
        redis_client.delete(key)  # 释放执行权，允许重试

        raise


@celery_app.task(bind=True, name="app.task.stock_init_task.update_stock_daily_all")
def update_stock_daily_all(self):
    from app.service.factory.stock_service_factory import create_stock_service
    logger.info("celery task: update_stock_daily_all任务启动")
    start_date = (datetime.now() - timedelta(days=7)).date().strftime("%Y-%m-%d")
    end_date = datetime.now().date().strftime("%Y-%m-%d")
    with UnitOfWork() as uow:
        stock_service = create_stock_service(uow.db)
        stock_service.create_fetch_task(start_date, end_date)
    logger.info("celery task: update_stock_daily_all任务结束")


@celery_app.task(bind=True, name="app.task.stock_init_task.update_stock_basic_delta")
def update_stock_basic_delta(self):
    from app.service.factory.stock_service_factory import create_stock_service
    logger.info("celery task: update_stock_basic_delta任务启动")
    with UnitOfWork() as uow:
        stock_service = create_stock_service(uow.db)
        stock_service.update_stock_basic_delta()
    logger.info("celery task: update_stock_basic_delta任务结束")


@celery_app.task(name="app.task.stock_init_task.clear_progress")
def clear_progress(task_id: UUID):
    db = SessionLocal()
    try:
        db.query(FetchProgress).filter(FetchProgress.task_id == task_id).delete()
        db.query(FetchTask).filter(FetchTask.task_id == task_id).delete()
        db.commit()
        progress_tracker.delete_task(task_id)
        return {"status": "cleared", "task_id": task_id}
    finally:
        db.close()
