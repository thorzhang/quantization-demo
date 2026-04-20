#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
import uuid

from pydantic import BaseModel, Field
from sqlalchemy.testing.pickleable import User


class UserCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=20)

    def to_entity(self) -> "User":
        return User(
            id=self.id,
            name=self.name
        )


class User(BaseModel):
    id: uuid.UUID
    name: str

    model_config = {
        "from_attributes": True  # Pydantic v2
    }
