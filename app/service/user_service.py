#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from uuid import UUID

from app.core.exception.exception import NotFoundException, ValidateErrorException
from app.repository.user_repository import UserRepository
from app.schema.user import User, UserCreate


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    def get_user(self, user_id: UUID) -> User:
        user = self.repo.get(user_id)
        if not user:
            raise NotFoundException(f"User {user_id} not found")
        return User.model_validate(user)

    def create_user(self, user_create: UserCreate) -> User:
        if "name" not in user_create:
            raise ValidateErrorException("name is required")

        user = user_create.to_entity()

        user = self.repo.create(user)
        return User.model_validate(user)
