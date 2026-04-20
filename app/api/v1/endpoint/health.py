#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def health_check():
    return {"status": "ok"}
