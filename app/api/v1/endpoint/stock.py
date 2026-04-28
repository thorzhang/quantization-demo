#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.dep.stock_dep import StockServiceDep
from app.model.fetch_progress import FetchProgress
from app.task.progress_tracker import progress_tracker

router = APIRouter()


@router.post("/init")
def init_stock(stock_service: StockServiceDep):
    stock_service.init_stock_list()
    return {"msg": "ok"}


@router.post("/fetch-all")
def fetch_all(stock_service: StockServiceDep):
    """
        启动全量抓取任务
        - **resume**: 是否启用断点续传（默认 True）
    """
    return stock_service.create_fetch_task()


@router.get("/task-status/{task_id}")
async def get_task_status(task_id: str):
    """
    获取任务进度
    """
    # 从 Redis 获取实时进度
    progress = progress_tracker.get_progress(task_id)

    if not progress:
        # 尝试从数据库获取
        from celery.result import AsyncResult

        from app.celery_app import celery_app
        result = AsyncResult(task_id, app=celery_app)
        if result.status == "PENDING":
            raise HTTPException(status_code=404, detail="Task not found")

        return {
            "task_id": task_id,
            "status": result.status,
            "result": result.result if result.ready() else None
        }

    return progress


@router.get("/task-status/{task_id}/detailed")
async def get_task_status_detailed(task_id: str, db: Session = Depends(get_db)):
    """
    获取详细任务状态（包含失败股票列表）
    """

    # 获取基本信息
    progress = progress_tracker.get_progress(task_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Task not found")

    # 获取失败的股票
    failed_stocks = db.query(FetchProgress).filter(
        FetchProgress.task_id == task_id,
        FetchProgress.status == "failed"
    ).limit(100).all()

    return {
        **progress,
        "failed_stocks": [
            {"symbol": fs.symbol, "error": fs.error_msg}
            for fs in failed_stocks
        ]
    }


@router.post("/task-cancel/{task_id}")
async def cancel_task(task_id: str):
    """
    取消正在执行的任务
    """
    from celery.result import AsyncResult
    from app.celery_app import celery_app

    result = AsyncResult(task_id, app=celery_app)

    if result.state in ["PENDING", "STARTED"]:
        result.revoke(terminate=True)
        return {"message": f"Task {task_id} cancelled", "status": result.state}

    return {"message": f"Task {task_id} cannot be cancelled (state: {result.state})", "status": result.state}


@router.delete("/task-clear/{task_id}")
async def clear_task(task_id: str):
    """
    清理任务进度记录
    """

    return {"message": f"Clearing task {task_id}", "cleanup_task": result.id}


@router.get("/tasks/running")
async def get_running_tasks():
    """
    获取正在运行的任务列表
    """
    from app.celery_app import celery_app

    inspect = celery_app.control.inspect()
    active = inspect.active()

    if not active:
        return {"running_tasks": []}

    tasks = []
    for worker, task_list in active.items():
        for task in task_list:
            tasks.append({
                "worker": worker,
                "task_id": task["id"],
                "name": task["name"],
                "args": task["args"],
                "kwargs": task["kwargs"]
            })

    return {"running_tasks": tasks}
