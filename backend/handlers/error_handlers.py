#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异常处理器模块
处理各种HTTP错误的响应
"""

import os
import uuid
from datetime import datetime
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError

from ..core.config import FRONTEND_ROOT_DIR


def get_error_id() -> str:
    """生成唯一的错误ID"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{timestamp}-{str(uuid.uuid4())[:4]}"


def get_base_url(request: Request) -> str:
    """获取请求的基础URL"""
    scheme = request.url.scheme
    host = request.headers.get('Host', 'localhost')
    return f'{scheme}://{host}'


def is_html_request(request: Request) -> bool:
    """判断是否为HTML请求（浏览器直接访问）"""
    # 1. 检查是否为AJAX请求（传统XHR）
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return False
    
    # 2. 检查是否为现代Fetch API请求（由网页自动发起）
    sec_fetch_mode = request.headers.get('Sec-Fetch-Mode', '')
    sec_fetch_dest = request.headers.get('Sec-Fetch-Dest', '')
    sec_fetch_site = request.headers.get('Sec-Fetch-Site', '')
    
    # 现代网页API请求特征
    is_modern_api_request = (
        sec_fetch_mode in ['cors', 'same-origin'] and
        sec_fetch_dest in ['empty', 'api'] and
        sec_fetch_site in ['same-origin', 'cross-site']
    )
    
    if is_modern_api_request:
        return False
    
    # 3. 检查请求头信息
    accept_header = request.headers.get('Accept', '')
    user_agent = request.headers.get('User-Agent', '')
    
    # 4. 判断是否为浏览器用户代理
    is_browser = any(browser in user_agent.lower() for browser in 
                    ['mozilla', 'chrome', 'safari', 'edge', 'opera'])
    
    # 5. 判断是否请求HTML
    is_html_accept = 'text/html' in accept_header or accept_header == '*/*'
    
    # 6. 综合判断：浏览器直接访问返回HTML，其他访问返回JSON
    if is_browser and is_html_accept:
        return True
    
    return False


def render_error_page(template_path: str, context: dict) -> str:
    """渲染错误页面"""
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()

        for key, value in context.items():
            placeholder = '{{' + key + '}}'
            content = content.replace(placeholder, str(value) if value is not None else '')

        return content
    except Exception as e:
        print(f"[ERROR] 读取错误页面失败: {str(e)}")
        return ""


async def not_found_handler(request: Request, exc: HTTPException):
    """自定义404错误处理"""
    base_url = get_base_url(request)
    return await create_error_response(
        request, 
        "404页面不存在", 
        404, 
        {"page_url": request.url.path, "BASE_URL": base_url}, 
        exc.detail or "页面不存在"
    )


async def internal_error_handler(request: Request, exc: Exception):
    """自定义500错误处理"""
    error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return await create_error_response(
        request, 
        "500服务器内部错误", 
        500, 
        {"error_time": error_time}, 
        str(exc) if str(exc) else "服务器内部错误"
    )


async def validation_error_handler(request: Request, exc: RequestValidationError):
    """自定义400错误处理"""
    base_url = get_base_url(request)
    
    # 提取错误详情
    detail = "参数错误"
    if exc.errors:
        detail = exc.errors()[0].get('msg', '参数错误')
    
    return await create_error_response(
        request, 
        "400参数错误", 
        400, 
        {"reason": detail, "BASE_URL": base_url}, 
        detail
    )


async def create_error_response(request: Request, error_type: str, status_code: int, context: dict = None, detail: str = None):
    """
    创建错误响应
    
    Args:
        request: Request对象，用于判断请求类型和获取请求信息
        error_type: 错误类型，如 "404分类不存在"、"404图片不存在" 等
        status_code: HTTP状态码
        context: 错误页面模板上下文，用于替换占位符
        detail: 错误详情，用于JSON响应
        
    Returns:
        HTMLResponse或JSONResponse对象
    """
    from fastapi.responses import HTMLResponse, JSONResponse
    from ..utils.utils import get_error_page
    from ..utils.utils import get_client_ip
    
    # 生成唯一错误ID
    error_id = get_error_id()
    error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    client_ip = get_client_ip(
        request.headers.get('X-Forwarded-For', ''),
        request.client.host if request.client else 'unknown'
    )
    
    # 记录错误日志
    print(f"[ERROR] {error_time} - {status_code} - {error_type} - {detail or ''} - Error ID: {error_id}")
    print(f"[ERROR] 请求地址: {request.url.path} - IP: {client_ip}")
    print(f"[ERROR] 请求头: {dict(request.headers)}")
    
    # 更新上下文，添加错误ID
    if context is None:
        context = {}
    context['error_id'] = error_id
    context['error_time'] = error_time
    
    if is_html_request(request):
        # 网页请求返回错误页面
        content = await get_error_page(error_type, context)
        if content:
            return HTMLResponse(content=content, status_code=status_code)
        # 如果错误页面不存在，返回默认HTML响应
        return HTMLResponse(content=f"Error {status_code}: {detail or error_type}", status_code=status_code)
    else:
        # 非网页请求返回JSON响应
        return JSONResponse(content={
            "code": status_code,
            "msg": detail or error_type,
            "data": {
                "error_id": error_id,
                "error_time": error_time
            }
        }, status_code=status_code)
