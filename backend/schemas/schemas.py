#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pydantic 请求模型
=================

只保留路由实际使用的模型。响应体统一用 JSONResponse 直接构造，
不再维护一整套与实现脱节的 Response 模型（原先 20 个模型里 15 个从未被引用）。
"""

from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """用户注册请求"""
    username: str = Field(..., min_length=3, max_length=16, description="用户名，3-16位字母、数字、下划线")
    email: EmailStr = Field(..., description="邮箱地址")
    password: str = Field(..., min_length=6, description="密码，至少6位")


class LoginRequest(BaseModel):
    """用户登录请求"""
    account: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., min_length=6, description="密码")
    remember: bool = False


class UserCreateRequest(BaseModel):
    """创建用户（管理员）"""
    username: str = Field(..., min_length=3, max_length=16)
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=6)


class UserUpdateRequest(BaseModel):
    """更新用户（管理员）

    password / role 为可选：管理员可以顺手重置密码或调整角色。
    """
    username: str = Field(..., min_length=3, max_length=16)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=6, max_length=64)
    role: Optional[str] = Field(None, pattern=r'^(admin|user|vip)$')

    @field_validator('password', 'role', mode='before')
    @classmethod
    def _blank_to_none(cls, value):
        """前端表单没填时会传空串，这里当成"不修改"处理"""
        if isinstance(value, str) and not value.strip():
            return None
        return value
