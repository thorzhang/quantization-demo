#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""

from app.strategy.base import BaseStrategy
from app.strategy.momentum_strategy import MomentumStrategy


class StrategySelector:

    @staticmethod
    def get_strategy(name: str) -> BaseStrategy:
        if name == "momentum":
            return MomentumStrategy()

        raise ValueError(f"Unknown strategy: {name}")
