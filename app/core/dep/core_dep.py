#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from typing import Generator

from app.db.uow import UnitOfWork


def get_uow() -> Generator[UnitOfWork, None, None]:
    with UnitOfWork() as uow:
        yield uow
