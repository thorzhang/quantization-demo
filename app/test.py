#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from app.integration.datasource.baostock import BaostockSource
from app.integration.datasource.tencent import TencentSource

try:
    bs = BaostockSource()
    datas = bs.fetch_one_history("300200", "1970-01-01", "2026-05-06")

except Exception as e:
    tx = TencentSource()
    datas = tx.fetch_one_history("300200", "1970-01-01", "2026-05-06")

print(datas)
