#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from app.strategy.base import BaseStrategy
from app.strategy.robust_trend_strategy import RobustTrendStrategy


class StrategySelector:

    @staticmethod
    def get_strategy(name: str) -> BaseStrategy:
        if name == "robust_trend":
            return RobustTrendStrategy()

        raise ValueError(f"Unknown strategy: {name}")
