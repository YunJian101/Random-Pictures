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

from ..config import FRONTEND_ROOT_DIR


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
    """判断是否为HTML请求"""
    accept_header = request.headers.get('Accept', '')
    return 'text/html' in accept_header or accept_header == '*/*'


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
    error_id = get_error_id()
    error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    base_url = get_base_url(request)

    if is_html_request(request):
        template_path = os.path.join(FRONTEND_ROOT_DIR, 'Status_Code', '404页面不存在.html')
        if os.path.exists(template_path):
            content = render_error_page(template_path, {
                'page_url': request.url.path,
                'BASE_URL': base_url
            })
            if content:
                return HTMLResponse(content=content, status_code=404)
        return HTMLResponse(content="Page Not Found", status_code=404)
    else:
        return JSONResponse(content={
            "code": 404,
            "msg": "页面不存在",
            "data": {
                "error_id": error_id,
                "error_time": error_time,
                "path": request.url.path
            }
        }, status_code=404)


async def internal_error_handler(request: Request, exc: Exception):
    """自定义500错误处理"""
    error_id = get_error_id()
    error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if is_html_request(request):
        template_path = os.path.join(FRONTEND_ROOT_DIR, 'Status_Code', '500服务器内部错误.html')
        if os.path.exists(template_path):
            content = render_error_page(template_path, {
                'error_id': error_id,
                'error_time': error_time
            })
            if content:
                return HTMLResponse(content=content, status_code=500)
        return HTMLResponse(content="Internal Server Error", status_code=500)
    else:
        return JSONResponse(content={
            "code": 500,
            "msg": "服务器内部错误",
            "data": {
                "error_id": error_id,
                "error_time": error_time
            }
        }, status_code=500)


async def validation_error_handler(request: Request, exc: HTTPException):
    """自定义422错误处理"""
    request_id = get_error_id()
    error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    base_url = get_base_url(request)

    if is_html_request(request):
        template_path = os.path.join(FRONTEND_ROOT_DIR, 'Status_Code', '422非法请求.html')
        if os.path.exists(template_path):
            content = render_error_page(template_path, {
                'request_id': request_id,
                'reason': exc.detail or "非法请求",
                'BASE_URL': base_url
            })
            if content:
                return HTMLResponse(content=content, status_code=422)
        return HTMLResponse(content="Unprocessable Entity", status_code=422)
    else:
        return JSONResponse(content={
            "code": 422,
            "msg": "非法请求",
            "data": {
                "request_id": request_id,
                "error_time": error_time,
                "reason": exc.detail,
                "path": request.url.path
            }
        }, status_code=422)
