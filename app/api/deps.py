#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from typing import Annotated, Generator

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from app.core.exception.exceptions import ForbiddenException
from app.core.security.jwt import verify_token
from app.db.uow import UnitOfWork
from app.repository.user_repository import UserRepository
from app.schema.user import User
from app.service.user_service import UserService


# 👉 UoW（每请求）
def get_uow() -> Generator[UnitOfWork, None, None]:
    with UnitOfWork() as uow:
        yield uow


def get_user_repo(uow: UnitOfWork = Depends(get_uow)) -> UserRepository:
    return uow.get_repo(UserRepository)


def get_user_service(
        repo: UserRepository = Depends(get_user_repo)
) -> UserService:
    return UserService(repo)


# 👉 类型别名（简化 endpoint）
UserServiceDep = Annotated[UserService, Depends(get_user_service)]

# 告诉 FastAPI：token 从 Authorization: Bearer xxx 来
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    payload = verify_token(token)

    if not payload:
        raise ForbiddenException("用户未登录")

    return User(**payload)


UserDep = Annotated[User, Depends(get_current_user)]
