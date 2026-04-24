#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""

import akshare as ak

from app.integration.datasource.tencent import TencentSource

datasource = TencentSource()

df = ak.stock_zh_a_hist_tx(symbol='sz000001')
print("列名:", df.columns.tolist())  # 查看实际列名
print(df.head())
