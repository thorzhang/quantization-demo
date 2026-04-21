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
from app.repository.stock_repository import StockRepository
from app.service.stock_service import StockService


def get_stock_repo(uow: UnitOfWork = Depends(get_uow)) -> StockRepository:
    return uow.get_repo(StockRepository)


def get_stock_service(
        repo: StockRepository = Depends(get_stock_repo)
) -> StockService:
    return StockService(repo)


StockServiceDep = Annotated[StockService, Depends(get_stock_service)]
