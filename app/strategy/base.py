#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from abc import ABC, abstractmethod
from typing import List

import pandas as pd


class BaseStrategy(ABC):

    @staticmethod
    def reason() -> List[str]:
        """
        量化策略原因
        """
        pass

    @abstractmethod
    def generate_signals(self, df_raw: pd.DataFrame, max_positions=8, min_score=0.5, start_date=None, end_date=None):
        pass

    @abstractmethod
    def backtest(self, df, initial_capital=1000000, transaction_cost=0.0005,
                 max_positions=8, stop_loss=-0.05, take_profit=0.08,
                 rebalance_days=10):
        pass

    @abstractmethod
    def evaluate(self, results, trades, initial_capital=1000000):
        pass
