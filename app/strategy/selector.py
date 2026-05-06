#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from app.strategy.base import BaseStrategy
from app.strategy.ma_volume_strategy import MAVolumeStrategy


class StrategySelector:

    @staticmethod
    def get_strategy(name: str) -> BaseStrategy:
        if name == "ma_volume":
            return MAVolumeStrategy()

        raise ValueError(f"Unknown strategy: {name}")
