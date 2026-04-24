#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import json
from typing import Callable, Awaitable

from fastapi import Request
from fastapi.responses import JSONResponse, Response as FastAPIResponse
from starlette.responses import Response, StreamingResponse

from app.core.exception.exception_registry import exception_registry
from app.core.response.http_code import HttpCode
from app.core.response.response import Response as CustomResponse


async def response_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    try:
        response = await call_next(request)

        # 1. 流式响应直接放行（文件/流）
        if isinstance(response, StreamingResponse):
            return response

        # 2. 非标准 Response 直接放行
        if not isinstance(response, FastAPIResponse):
            return response

        # 3. 读取 body
        body = b""
        async for chunk in response.body_iterator:
            body += chunk

        # 解析 JSON
        try:
            data = json.loads(body) if body else None
        except Exception:
            data = body.decode() if body else None

        # 4. 统一响应结构
        resp = CustomResponse(
            code=HttpCode.SUCCESS,
            message="success",
            data=data,
        )

        return JSONResponse(
            status_code=response.status_code,
            content=resp.model_dump(mode="json"),
        )

    except Exception as exc:
        handler = exception_registry.get_handler(exc)

        if handler:
            resp, status = handler(exc)
            return JSONResponse(
                status_code=status,
                content=resp.model_dump(mode="json"),
            )

        # fallback
        resp = CustomResponse(
            code=HttpCode.FAIL,
            message=str(exc),
            data={},
        )

        return JSONResponse(
            status_code=500,
            content=resp.model_dump(mode="json"),
        )
