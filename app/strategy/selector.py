#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from app.strategy.base import BaseStrategy
from app.strategy.conservative_trend_strategy import ConservativeValueTrendStrategy
from app.strategy.ma_volume_strategy import MAVolumeStrategy


class StrategySelector:

    @staticmethod
    def get_strategy(name: str) -> BaseStrategy:
        if name == "ma_volume":
            return MAVolumeStrategy()
        elif name == "conservative_trend":
            return ConservativeValueTrendStrategy()

        raise ValueError(f"Unknown strategy: {name}")
