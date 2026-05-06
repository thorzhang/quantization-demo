#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from abc import ABC, abstractmethod
from typing import List

from app.core.enums.signal import Signal


class BaseStrategy(ABC):

    @abstractmethod
    def evaluate(self, data: List[dict]) -> Signal:
        """
        data: 已经整理好的K线数据（不能是ORM）
        """
        pass
