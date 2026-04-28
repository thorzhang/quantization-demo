#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from enum import Enum


class StockSource(str, Enum):
    BAOSTOCK = "baostock"
    EASTMONEY = "eastmoney"
    TENCENT = "tencent"
