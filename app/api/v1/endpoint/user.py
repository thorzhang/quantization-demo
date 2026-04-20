#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
@Time   : 2026/1/6   
@Author : zhanglei
@File   : app.py
"""
from uuid import UUID

from fastapi import APIRouter

from app.api.deps import UserServiceDep, UserDep
from app.core.response.response_route import ResponseAPIRoute
from app.core.security.jwt import create_access_token
from app.schema.user import User, UserCreate

router = APIRouter(route_class=ResponseAPIRoute)


@router.post("/login")
def login(user: User):
    # 实际应校验用户名密码

    token = create_access_token(user.model_dump(mode="json"))
    return {"access_token": token, "token_type": "bearer"}


@router.get("/profile")
def profile(current_user: UserDep):
    return current_user


@router.get("/{user_id}")
def get_user(user_id: UUID, user_service: UserServiceDep) -> User:
    return user_service.get_user(user_id)


@router.post("/")
def create_user(user: UserCreate, user_service: UserServiceDep) -> User:
    return user_service.create_user(user)
