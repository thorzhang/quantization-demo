#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from abc import ABC, abstractmethod
from typing import List, Dict


class BaseStrategy(ABC):

    @abstractmethod
    def evaluate(self, datas: dict) -> Dict:
        """
        data: 已经整理好的K线数据（不能是ORM）
        """
        pass

    @staticmethod
    def reason() -> List[str]:
        """
        量化策略原因
        """
        pass
