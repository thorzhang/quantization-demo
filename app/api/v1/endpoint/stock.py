#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from fastapi import APIRouter

from app.core.response.response_route import ResponseAPIRoute
from app.dep.stock_dep import StockServiceDep
from app.schema.stock import FetchStockRequest

router = APIRouter(route_class=ResponseAPIRoute)


@router.post("/info")
def fetch_stock_info(
        fetch_stock_request: FetchStockRequest,
        stock_service: StockServiceDep
):
    stock_service.fetch_and_store(fetch_stock_request.symbol)

    return {"msg": "ok"}
