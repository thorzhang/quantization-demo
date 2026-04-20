#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from app.db.database import SessionLocal


class UnitOfWork:
    def __init__(self):
        self.db = None
        self._repos = {}

    def __enter__(self):
        self.db = SessionLocal()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if exc_type:
                self.db.rollback()  # 出错回滚
            else:
                self.db.commit()  # 自动提交
        finally:
            self.db.close()

    # 懒加载 repository（关键优化）
    def get_repo(self, repo_cls):
        if repo_cls not in self._repos:
            self._repos[repo_cls] = repo_cls(self.db)
        return self._repos[repo_cls]
