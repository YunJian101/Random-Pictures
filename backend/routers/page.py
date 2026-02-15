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

from ..core.config import FRONTEND_ROOT_DIR
from ..core.database import get_db_connection
from ..api.dependencies import get_current_user, get_current_admin, get_current_user_optional


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
    from ..utils.utils import validate_local_path, is_remote_url
    
    # 从数据库获取favicon_url配置
    favicon_url = ''
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT config_value FROM system_configs WHERE config_key = %s', ('favicon_url',))
            result = cursor.fetchone()
            if result:
                favicon_url = result[0]
    except Exception as e:
        print(f"[ERROR] 获取favicon配置失败: {str(e)}")

    if favicon_url:
        # 检查是否为远程URL
        if is_remote_url(favicon_url):
            return RedirectResponse(url=favicon_url, status_code=302)
        else:
            # 本地路径验证
            is_valid, error_msg = validate_local_path(favicon_url)
            if not is_valid:
                print(f"[ERROR] 无效的favicon本地路径: {error_msg}")
                # 验证失败，使用默认favicon
            else:
                # 本地路径处理
                # 如果是相对路径，从前端静态目录开始查找
                if not favicon_url.startswith('/'):
                    favicon_path = os.path.join(FRONTEND_ROOT_DIR, favicon_url)
                else:
                    # 如果是绝对路径，尝试从前端静态目录开始查找
                    # 移除开头的/，然后从前端静态目录开始构建路径
                    favicon_path = os.path.join(FRONTEND_ROOT_DIR, favicon_url.lstrip('/'))
                
                # 如果指定的路径不存在，尝试在static目录中查找
                if not os.path.exists(favicon_path):
                    favicon_path = os.path.join(FRONTEND_ROOT_DIR, 'static', favicon_url.lstrip('/'))
                
                if os.path.exists(favicon_path):
                    return FileResponse(favicon_path)

    # 默认行为：尝试使用static目录中的favicon.ico
    favicon_path = os.path.join(FRONTEND_ROOT_DIR, 'static', 'favicon.ico')
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    raise HTTPException(status_code=404)
