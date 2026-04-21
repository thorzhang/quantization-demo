#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from pydantic import BaseModel


class FetchStockRequest(BaseModel):
    symbol: str
