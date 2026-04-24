#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from typing import Annotated

from fastapi import Depends

from app.core.dep.core_dep import get_uow
from app.db.uow import UnitOfWork
from app.repository.fetch_progress_repository import FetchProgressRepository
from app.repository.fetch_task_repository import FetchTaskRepository
from app.repository.stock_basic_repository import StockBasicRepository
from app.repository.stock_daily_repository import StockDailyRepository
from app.service.stock_service import StockService


def get_stock_basic_repo(uow: UnitOfWork = Depends(get_uow)) -> StockBasicRepository:
    return uow.get_repo(StockBasicRepository)


def get_stock_daily_repo(uow: UnitOfWork = Depends(get_uow)) -> StockDailyRepository:
    return uow.get_repo(StockDailyRepository)


def get_fetch_task_repo(uow: UnitOfWork = Depends(get_uow)) -> FetchTaskRepository:
    return uow.get_repo(FetchTaskRepository)


def get_fetch_progress_repo(uow: UnitOfWork = Depends(get_uow)) -> FetchProgressRepository:
    return uow.get_repo(FetchProgressRepository)


def get_stock_service(
        stock_basic_repo: StockBasicRepository = Depends(get_stock_basic_repo),
        stock_daily_repo: StockDailyRepository = Depends(get_stock_daily_repo),
        fetch_task_repo: FetchTaskRepository = Depends(get_fetch_task_repo),
        fetch_progress_repo: FetchProgressRepository = Depends(get_fetch_progress_repo)
) -> StockService:
    return StockService(stock_basic_repo, stock_daily_repo, fetch_task_repo, fetch_progress_repo)


StockServiceDep = Annotated[StockService, Depends(get_stock_service)]
