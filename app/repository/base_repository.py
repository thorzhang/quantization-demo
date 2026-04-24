#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from typing import TypeVar, Generic, Type, Optional, Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository(Generic[T]):
    model: Type[T]  # 由子类提供

    def __init__(self, db: Session):
        self.db = db

    # 新增
    def create(self, obj: T) -> T:
        self.db.add(obj)
        self.db.flush()  # 拿到ID等数据库生成字段
        return obj

    # 根据ID获取
    def get(self, id_: Any) -> Optional[T]:
        stmt = select(self.model).where(self.model.id == id_)
        return self.db.execute(stmt).scalar_one_or_none()

    # 更新（ORM方式）
    def update(self, obj: T, **kwargs) -> T:
        for key, value in kwargs.items():
            setattr(obj, key, value)
        self.db.flush()
        return obj

    # 更新（SQL方式，高性能）
    def update_by_id(self, id_: Any, **kwargs) -> None:
        stmt = (
            update(self.model)
            .where(self.model.id == id_)
            .values(**kwargs)
        )
        self.db.execute(stmt)
        self.db.flush()

    # 删除
    def delete(self, obj: T) -> None:
        self.db.delete(obj)
        self.db.flush()
