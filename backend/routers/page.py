#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
页面路由模块
处理所有页面访问请求
"""

import os
from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse
from fastapi import Request as FastAPIRequest

from ..config import FRONTEND_ROOT_DIR, FAVICON_URL
from ..dependencies import get_current_user, get_current_admin, get_current_user_optional


async def handle_index(request: FastAPIRequest, current_user: dict = Depends(get_current_user_optional)):
    """处理首页"""
    index_path = os.path.join(FRONTEND_ROOT_DIR, 'index.html')
    if os.path.exists(index_path):
        # 登录状态通过cookie传递给前端
        response = FileResponse(index_path)
        return response
    raise HTTPException(status_code=404, detail="首页文件不存在")


async def handle_login_page(request: FastAPIRequest, current_user: dict = Depends(get_current_user_optional)):
    """处理登录页面 - 已登录则重定向"""
    if current_user:
        return RedirectResponse(url='/', status_code=302)

    login_path = os.path.join(FRONTEND_ROOT_DIR, '注册登录界面.html')
    if os.path.exists(login_path):
        return FileResponse(login_path)
    raise HTTPException(status_code=404, detail="登录页面不存在")


async def handle_admin_panel(request: FastAPIRequest, current_user: dict = Depends(get_current_admin)):
    """处理管理后台页面 - 需要管理员权限"""
    admin_path = os.path.join(FRONTEND_ROOT_DIR, '管理后台.html')
    if os.path.exists(admin_path):
        return FileResponse(admin_path)
    raise HTTPException(status_code=404, detail="管理后台页面不存在")


async def handle_user_panel(request: FastAPIRequest, current_user: dict = Depends(get_current_user)):
    """处理用户后台页面 - 需要登录"""
    user_path = os.path.join(FRONTEND_ROOT_DIR, '用户后台.html')
    if os.path.exists(user_path):
        return FileResponse(user_path)
    raise HTTPException(status_code=404, detail="用户后台页面不存在")


async def handle_favicon():
    """处理favicon请求"""
    if FAVICON_URL:
        return RedirectResponse(url=FAVICON_URL, status_code=302)

    favicon_path = os.path.join(FRONTEND_ROOT_DIR, 'static', 'favicon.ico')
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    raise HTTPException(status_code=404)
