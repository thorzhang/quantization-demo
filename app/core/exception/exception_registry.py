#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from typing import Dict, Type, Callable, Optional, TypeVar, Any

T = TypeVar("T", bound=Callable[..., Any])


class ExceptionRegistry:
    def __init__(self):
        self._handlers: Dict[Type[Exception], Callable[..., Any]] = {}

    def register(self, exc_type: Type[Exception]) -> Callable[[T], T]:
        def wrapper(func: T) -> T:
            self._handlers[exc_type] = func
            return func

        return wrapper

    def get_handler(self, exc: Exception) -> Optional[Callable[..., Any]]:
        for exc_type, handler in self._handlers.items():
            if isinstance(exc, exc_type):
                return handler
        return None


exception_registry = ExceptionRegistry()
