#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from typing import Tuple

from app.core.exception.exception_registry import exception_registry
from app.core.exception.exceptions import NotFoundException, AppException, ValidateErrorException
from app.core.response.response import Response


@exception_registry.register(NotFoundException)
def handle_not_found(exc: NotFoundException) -> Tuple[Response, int]:
    return Response(
        code=exc.code,
        message=exc.message,
        data={}
    ), 404


@exception_registry.register(ValidateErrorException)
def handle_validate_error_exception(exc: ValidateErrorException) -> Tuple[Response, int]:
    return Response(
        code=exc.code,
        message=exc.message,
        data={}
    ), 412


@exception_registry.register(AppException)
def handle_app_exception(exc: AppException) -> Tuple[Response, int]:
    return Response(
        code=exc.code,
        message=exc.message,
        data={}
    ), 500
