#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pydantic模型定义
================

定义API请求和响应的数据模型
"""

from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# ==================== 通用响应模型 ====================
class APIResponse(BaseModel):
    """通用API响应"""
    code: int
    msg: str
    data: Optional[dict] = None


class ErrorResponse(BaseModel):
    """错误响应"""
    code: int
    msg: str
    data: Optional[dict] = None


# ==================== 认证相关模型 ====================
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


class LogoutRequest(BaseModel):
    """用户登出请求"""
    pass


class VerifyResponse(BaseModel):
    """会话验证响应"""
    code: int
    msg: str
    data: Optional['UserData'] = None


class UserData(BaseModel):
    """用户数据"""
    id: int
    username: str
    email: str
    role: str


class LoginResponse(BaseModel):
    """登录响应"""
    code: int
    msg: str
    data: Optional[dict] = None


# ==================== 用户相关模型 ====================
class UserResponse(BaseModel):
    """用户信息响应"""
    id: int
    user_id: str
    username: str
    email: str
    role: str
    avatar: str
    created_at: str
    last_login_ip: str
    is_banned: bool


class UserListResponse(BaseModel):
    """用户列表响应"""
    code: int
    msg: str
    data: dict


class UserUpdateRequest(BaseModel):
    """更新用户请求"""
    username: str = Field(..., min_length=3, max_length=16)
    email: Optional[EmailStr] = None


class UserCreateRequest(BaseModel):
    """创建用户请求（管理员）"""
    username: str = Field(..., min_length=3, max_length=16)
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=6)


class CreateAdminRequest(BaseModel):
    """创建管理员请求"""
    username: str = Field(..., min_length=3, max_length=16)
    email: Optional[EmailStr] = None
    password: str = Field(..., min_length=6)


# ==================== 图片相关模型 ====================
class ImageInfo(BaseModel):
    """图片信息"""
    name: str
    url: str
    path: str


class CategoriesResponse(BaseModel):
    """分类列表响应"""
    categories: dict
    current_page: int
    total_pages: int
    total_categories: int
    items_per_page: int


class CategoryImagesResponse(BaseModel):
    """分类图片响应"""
    category_name: str
    images: List[ImageInfo]
    current_page: int
    total_pages: int
    total_images: int
    page_size: int


# ==================== 配置相关模型 ====================
class ConfigResponse(BaseModel):
    """配置信息响应"""
    version: str
    icp_beian_code: str
    icp_beian_url: str
    code: int = 200
    msg: str = "success"


# ==================== 错误信息模型 ====================
class ErrorInfo(BaseModel):
    """错误信息"""
    error_id: str
    error_time: str


class CategoryNotFoundError(ErrorInfo):
    """分类不存在错误"""
    category: str


class ImageNotFoundError(ErrorInfo):
    """图片不存在错误"""
    image_path: str
