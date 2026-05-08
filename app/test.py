#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from app.integration.datasource.baostock import BaostockSource

try:
    bs = BaostockSource()
    datas = bs.fetch_one_history("002455", "2026-05-07", "2026-05-07")

except Exception as e:
    pass

print(datas)
