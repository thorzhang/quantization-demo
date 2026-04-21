#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""

import akshare as ak

start_date = "20260401"
end_date = "20260420"

print("DEBUG:", start_date, type(start_date))

df = ak.stock_zh_a_hist(
    symbol="000001",  # 添加了 'sz' 前缀
    start_date=start_date,
    end_date=end_date,
    adjust="qfq"  # 建议显式指定复权方式
)

print(df.head(30))
