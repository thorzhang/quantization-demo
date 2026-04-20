#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from typing import TypeVar, Generic, Optional

from pydantic import BaseModel

from app.core.response.http_code import HttpCode

T = TypeVar("T")


class Response(BaseModel, Generic[T]):
    """基础HTTP接口响应格式"""
    code: HttpCode = HttpCode.SUCCESS
    message: str = ""
    data: Optional[T] = None
