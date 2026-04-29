#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from app.integration.datasource.baostock import BaostockSource

symbol = "000001"

bs = BaostockSource()
bs.fetch_one_history("000001")
