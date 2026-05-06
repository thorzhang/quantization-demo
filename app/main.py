#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.log.logging import init_logging
from app.middleware.response_middleware import response_middleware

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 日志初始化
    service_name = os.getenv("SERVICE_NAME", "app")
    init_logging(service_name)

    yield


def create_app() -> FastAPI:
    # 不能删掉这句话，必须强制注册异常处理器，否则的话，处理器无效。

    fastapi_app = FastAPI(
        title="My Quantization Project",
        version="1.0.0",
        lifespan=lifespan,
    )

    # 注册路由
    fastapi_app.include_router(api_router, prefix="/api/v1")

    fastapi_app.middleware("http")(response_middleware)

    return fastapi_app


app = create_app()
