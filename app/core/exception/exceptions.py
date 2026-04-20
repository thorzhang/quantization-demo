#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from dataclasses import field
from typing import Any

from app.core.response.http_code import HttpCode


class AppException(Exception):
    """基础自定义异常信息"""
    code: HttpCode = HttpCode.FAIL
    message: str = ""
    data: Any = field(default_factory=dict)

    def __init__(self, message: str = None, data: Any = None):
        super().__init__()
        self.message = message
        self.data = data


class NotFoundException(AppException):
    """未找到数据异常"""
    code = HttpCode.NOT_FOUND


class UnauthorizedException(AppException):
    """未授权异常"""
    code = HttpCode.UNAUTHORIZED


class ForbiddenException(AppException):
    """无权限异常"""
    code = HttpCode.FORBIDDEN


class ValidateErrorException(AppException):
    """数据验证异常"""
    code = HttpCode.VALIDATE_ERROR
