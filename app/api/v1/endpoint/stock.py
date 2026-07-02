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
from app.dep.backtest_dep import SignalBacktestServiceDep
from app.dep.stock_dep import StockServiceDep
from app.model.fetch_progress import FetchProgress
from app.schema.fetch_task_schema import FetchTaskCreateRequest
from app.schema.stock_daily_schema import StockRecommendRequest, StockBackTestRequest
from app.task.progress_tracker import progress_tracker

router = APIRouter()


@router.post("/basic/all")
def update_stock_basic_delta(stock_service: StockServiceDep):
    stock_service.update_stock_basic_delta()
    return {"msg": "ok"}


@router.post("/daily/all")
def update_stock_daily_all(fetch_task_create_request: FetchTaskCreateRequest, stock_service: StockServiceDep):
    return stock_service.create_fetch_task(fetch_task_create_request)


@router.post("/daily/recommend")
def get_recommend_stocks(stock_recommend_request: StockRecommendRequest,
                         signal_backtest_service: SignalBacktestServiceDep):
    result = signal_backtest_service.get_daily_trading_signal(
        strategy_name=stock_recommend_request.strategy_name,
        current_positions=stock_recommend_request.current_positions,
        cash=stock_recommend_request.cash,
        max_positions=stock_recommend_request.max_positions,
        stop_loss=stock_recommend_request.stop_loss,
        take_profit=stock_recommend_request.take_profit,
        rebalance_days=stock_recommend_request.rebalance_days,
        min_score=stock_recommend_request.min_score,
        transaction_cost=stock_recommend_request.transaction_cost,
    )
    # result = {'buy_list': [], 'execution_date': '2026-06-10', 'hold_list': [], 'sell_list_today': [],
    #           'sell_list_tomorrow': [], 'signal_date': '2026-06-09', 'stop_loss_today': False,
    #           'summary': {'active_holdings': 0, 'available_cash': 100000.0, 'avg_score_buy': 0, 'current_positions': 0,
    #                       'market_ok': False, 'reason_stats': {'signal_lost': 0, 'stop_loss': 0, 'take_profit': 0},
    #                       'sell_today': 0, 'sell_tomorrow': 0, 'signal_count': 0, 'suggest_buy': 0,
    #                       'suggest_buy_cash': 0,
    #                       'suggest_hold': 0, 'total_candidates': 1681}, 'updated_cash': 100000.0}
    return result


@router.post("/backtest/run")
def run_backtest(stock_back_test_request: StockBackTestRequest, stock_service: StockServiceDep):
    result = stock_service.run_signal_backtest(
        strategy_name=stock_back_test_request.strategy_name,
        start_date=stock_back_test_request.start_date,
        end_date=stock_back_test_request.end_date,
        top_k=stock_back_test_request.top_k,
        min_history=stock_back_test_request.min_history,
        take_profit=stock_back_test_request.take_profit,
        stop_loss=stock_back_test_request.stop_loss,
        max_hold_days=stock_back_test_request.max_hold_days,
        max_single_position_pct=stock_back_test_request.max_single_position_pct,
        market_width_sample_size=stock_back_test_request.market_width_sample_size,
        market_width_frequency=stock_back_test_request.market_width_frequency
    )

    return result


@router.post("/backtest/signal/run")
def run_backtest(request: StockBackTestRequest, signal_backtest_service: SignalBacktestServiceDep):
    result = signal_backtest_service.run_backtest(
        strategy_name=request.strategy_name,
        start_date=request.start_date,
        end_date=request.end_date,
        top_k=request.top_k,
        init_cash=request.init_cash,
        min_history=request.min_history,
    )

    return result


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
