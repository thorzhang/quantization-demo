#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6
@Author : zhanglei
@File   : app.py
"""
from typing import Awaitable, Callable

from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response as FastAPIResponse
from fastapi.routing import APIRoute
from starlette.requests import Request
from starlette.responses import JSONResponse, Response as StarletteResponse

from app.core.exception.exception_registry import exception_registry
from app.core.response.http_code import HttpCode
from app.core.response.response import Response


class ResponseAPIRoute(APIRoute):

    def get_route_handler(self) -> Callable[[Request], Awaitable[StarletteResponse]]:
        original_handler = super().get_route_handler()

        async def custom_handler(request: Request) -> StarletteResponse:
            try:
                result = await original_handler(request)

                # 1. 原生 Response 直接放行（stream/file/json 等）
                if isinstance(result, FastAPIResponse):
                    return result

                # 2. 构造统一响应（Pydantic v2）
                resp = Response(
                    code=HttpCode.SUCCESS,
                    message="success",
                    data=result,
                )

                return JSONResponse(
                    status_code=200,
                    content=jsonable_encoder(resp),
                )

            except Exception as exc:

                handler = exception_registry.get_handler(exc)

                if handler:
                    resp, status = handler(exc)
                    return JSONResponse(
                        status_code=status,
                        content=jsonable_encoder(resp),
                    )

                # fallback
                resp = Response(
                    code=HttpCode.FAIL,
                    message=str(exc),
                    data={},
                )

                return JSONResponse(
                    status_code=500,
                    content=jsonable_encoder(resp),
                )

        return custom_handler
