#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from uuid import UUID

from sqlalchemy.orm import Session

from app.model.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, user_id: UUID):
        return self.db.query(User).filter(User.id == user_id).first()

    def create(self, user: User):
        self.db.add(user)
        self.db.flush()  # 获取 id
        return user
