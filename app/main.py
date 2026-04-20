#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""

from dotenv import load_dotenv
from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.response.response_route import ResponseAPIRoute

load_dotenv()


def create_app() -> FastAPI:
    # 不能删掉这句话，必须强制注册异常处理器，否则的话，处理器无效。
    import app.core.exception.exception_handlers

    app = FastAPI(
        title="My FastAPI Project",
        version="1.0.0",
        route_class=ResponseAPIRoute
    )

    # 注册路由
    app.include_router(api_router, prefix="/api/v1")

    return app


app = create_app()
print(app.routes)
