#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI随机图API - 主应用
=========================

使用FastAPI重构的随机图片API服务
"""

import os
import uuid
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response, Depends, HTTPException, Query, Cookie
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import uvicorn

from .config import (
    PORT, HOST, IMG_ROOT_DIR, STATIC_ROOT_DIR, FRONTEND_ROOT_DIR,
    SITE_NAME, FAVICON_URL, ICP_BEIAN_CODE, ICP_BEIAN_URL,
    HOME_PAGE_SIZE, CATEGORY_PAGE_SIZE, COOKIE_NAME,
    ALLOW_ORIGINS, ALLOW_METHODS, ALLOW_HEADERS,
    COOKIE_MAX_AGE
)
from .database import init_db
from .auth import (
    register_user, login_user, logout_user, verify_session,
    get_user_by_id, get_all_users, update_user_info,
    ban_user, unban_user, delete_user, update_user_role
)
from .image_service import (
    get_paginated_categories, get_paginated_category_images,
    get_random_image_in_category, get_random_image_in_all_categories
)
from .utils import (
    validate_safe_path, validate_image_file,
    get_mime_type, get_client_ip
)
from .schemas import *
from .dependencies import (
    get_current_user,
    get_current_user_optional,
    get_current_admin,
    optional_auth,
    require_auth,
    require_admin
)


# ==================== 日志中间件 ====================
class LoggingMiddleware(BaseHTTPMiddleware):
    """请求日志中间件"""

    async def dispatch(self, request: Request, call_next):
        start_time = datetime.now()

        # 获取客户端IP
        x_forwarded_for = request.headers.get('X-Forwarded-For', '')
        client_ip = get_client_ip(x_forwarded_for, request.client.host if request.client else '')

        # 处理请求
        response = await call_next(request)

        # 计算处理时间
        process_time = (datetime.now() - start_time).total_seconds()

        # 记录日志
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {client_ip} - {request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s")

        return response


# ==================== 应用生命周期 ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    print(f"\n{'=' * 50}")
    print(f"🚀 {SITE_NAME} 启动中...")
    print(f"{'=' * 50}")

    # 确保目录存在
    Path(IMG_ROOT_DIR).mkdir(parents=True, exist_ok=True)
    Path(STATIC_ROOT_DIR).mkdir(parents=True, exist_ok=True)
    Path(FRONTEND_ROOT_DIR).mkdir(parents=True, exist_ok=True)

    # 初始化数据库
    init_db()
    print("✅ 数据库初始化完成")

    yield

    # 关闭时清理
    print("\n🔄 正在关闭服务...")
    print("✅ 服务已关闭")


# ==================== 创建FastAPI应用 ====================
app = FastAPI(
    title="随机图API",
    description="一个高性能的随机图片API服务",
    version="3.0.0",
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOW_ORIGINS if ALLOW_ORIGINS != ['*'] else ['*'],
    allow_credentials=True,
    allow_methods=ALLOW_METHODS,
    allow_headers=ALLOW_HEADERS,
)

# 添加日志中间件
app.add_middleware(LoggingMiddleware)

# 挂载静态文件目录
if os.path.exists(STATIC_ROOT_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_ROOT_DIR), name="static")


# ==================== 辅助函数 ====================
def get_base_url(request: Request) -> str:
    """获取请求的基础URL"""
    scheme = request.url.scheme
    host = request.headers.get('Host', 'localhost')
    return f'{scheme}://{host}'


def get_error_id() -> str:
    """生成唯一的错误ID"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{timestamp}-{str(uuid.uuid4())[:4]}"


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


# ==================== 首页路由 ====================
@app.get("/", response_class=HTMLResponse)
async def handle_index(request: Request):
    """处理首页"""
    index_path = os.path.join(FRONTEND_ROOT_DIR, 'index.html')
    if os.path.exists(index_path):
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="首页文件不存在")


@app.get("/login", response_class=HTMLResponse)
async def handle_login_page(request: Request, current_user: Optional[dict] = Depends(lambda r: get_current_user(r, optional=True))):
    """处理登录页面 - 已登录则重定向"""
    if current_user:
        return RedirectResponse(url='/', status_code=302)

    login_path = os.path.join(FRONTEND_ROOT_DIR, '注册登录界面.html')
    if os.path.exists(login_path):
        return FileResponse(login_path)
    raise HTTPException(status_code=404, detail="登录页面不存在")


@app.get("/admin-panel", response_class=HTMLResponse)
async def handle_admin_panel(request: Request, current_user: dict = Depends(get_current_admin)):
    """处理管理后台页面 - 需要管理员权限"""
    admin_path = os.path.join(FRONTEND_ROOT_DIR, '管理后台.html')
    if os.path.exists(admin_path):
        return FileResponse(admin_path)
    raise HTTPException(status_code=404, detail="管理后台页面不存在")


@app.get("/user-panel", response_class=HTMLResponse)
async def handle_user_panel(request: Request, current_user: dict = Depends(get_current_user)):
    """处理用户后台页面 - 需要登录"""
    user_path = os.path.join(FRONTEND_ROOT_DIR, '用户后台.html')
    if os.path.exists(user_path):
        return FileResponse(user_path)
    raise HTTPException(status_code=404, detail="用户后台页面不存在")


# ==================== favicon路由 ====================
@app.get("/favicon.ico")
async def handle_favicon():
    """处理favicon请求"""
    if FAVICON_URL:
        return RedirectResponse(url=FAVICON_URL, status_code=302)

    favicon_path = os.path.join(FRONTEND_ROOT_DIR, 'static', 'favicon.ico')
    if os.path.exists(favicon_path):
        return FileResponse(favicon_path)
    raise HTTPException(status_code=404)


# ==================== API路由 - 分类和图片 ====================
@app.get("/api/categories")
async def api_categories(
    page: int = Query(1, ge=1, le=1000, description="页码")
):
    """分类列表API"""
    result = get_paginated_categories(page)
    return JSONResponse(content=result)


@app.get("/api/category/images")
async def api_category_images(
    name: str = Query(..., description="分类名称"),
    page: int = Query(1, ge=1, le=1000, description="页码")
):
    """分类图片API"""
    from urllib.parse import unquote
    result = get_paginated_category_images(unquote(name), page)
    return JSONResponse(content=result)


@app.get("/api/config")
async def api_config():
    """配置信息API"""
    from . import __version__
    return JSONResponse(content={
        "version": __version__,
        "icp_beian_code": ICP_BEIAN_CODE if ICP_BEIAN_CODE else "",
        "icp_beian_url": ICP_BEIAN_URL if ICP_BEIAN_URL else "https://beian.miit.gov.cn",
        "code": 200,
        "msg": "success"
    })


# ==================== 随机图片路由 ====================
@app.get("/random")
async def handle_random_image(
    request: Request,
    type: Optional[str] = Query(None, description="分类类型")
):
    """处理随机图片请求 - 直接返回图片内容"""
    from urllib.parse import unquote

    try:
        if type:
            decoded_category = unquote(type)
            result = get_random_image_in_category(decoded_category)
        else:
            result = get_random_image_in_all_categories()

        if result is None:
            if type:
                raise HTTPException(status_code=404, detail="分类不存在")
            raise HTTPException(status_code=404, detail="没有可用的图片")

        if isinstance(result, dict) and result.get('error') == 'empty':
            raise HTTPException(status_code=404, detail="该分类下没有图片")

        image_path = result.get('path')
        if not image_path:
            raise HTTPException(status_code=404, detail="无法获取图片路径")

        full_path = os.path.join(IMG_ROOT_DIR, image_path)

        if not os.path.exists(full_path) or not os.path.isfile(full_path):
            raise HTTPException(status_code=404, detail="图片文件不存在")

        if not validate_image_file(full_path):
            raise HTTPException(status_code=404, detail="不是有效的图片文件")

        content_type = get_mime_type(full_path)

        return FileResponse(
            full_path,
            media_type=content_type,
            headers={
                'Cache-Control': 'no-cache, max-age=0'
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] 处理随机图片请求时发生错误: {str(e)}")
        raise HTTPException(status_code=500, detail="处理随机图片请求时发生错误")


@app.get("/image")
async def handle_image(
    request: Request,
    path: str = Query(..., description="图片路径")
):
    """处理图片直链请求"""
    from urllib.parse import unquote

    if not validate_safe_path(IMG_ROOT_DIR, path):
        raise HTTPException(status_code=422, detail="非法图片路径")

    full_path = os.path.join(IMG_ROOT_DIR, unquote(path))

    if not os.path.exists(full_path):
        # 检查分类是否存在
        path_parts = path.split('/')
        if len(path_parts) > 1:
            category = path_parts[0]
            category_path = os.path.join(IMG_ROOT_DIR, category)
            if not os.path.isdir(category_path):
                raise HTTPException(status_code=404, detail="分类不存在")

        raise HTTPException(status_code=404, detail="图片不存在")

    if not validate_image_file(full_path):
        raise HTTPException(status_code=404, detail="图片不存在")

    content_type = get_mime_type(full_path)

    return FileResponse(
        full_path,
        media_type=content_type,
        headers={
            'Cache-Control': 'public, max-age=604800'
        }
    )


# ==================== 认证API路由 ====================
@app.post("/api/register")
async def api_register(data: RegisterRequest):
    """用户注册API"""
    result = register_user(data.username, data.email, data.password)
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


@app.post("/api/login")
async def api_login(data: LoginRequest, response: Response):
    """用户登录API"""
    result = login_user(data.account, data.password)

    # 设置token到cookie
    if result['code'] == 200:
        token = result['data']['token']
        max_age = COOKIE_MAX_AGE if data.remember else None
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            httponly=True,
            samesite='lax',
            max_age=max_age
        )

    status_code = 200 if result['code'] == 200 else 401
    return JSONResponse(content=result, status_code=status_code)


@app.post("/api/logout")
async def api_logout(response: Response, request: Request):
    """用户登出API"""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        logout_user(token)

    # 清除cookie
    response.delete_cookie(key=COOKIE_NAME)
    return JSONResponse(content={'code': 200, 'msg': '登出成功'})


@app.get("/api/auth/verify")
async def api_auth_verify(request: Request):
    """验证用户登录状态API"""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return JSONResponse(content={'code': 401, 'msg': '未登录'}, status_code=401)

    result = verify_session(token)
    status_code = 200 if result['code'] == 200 else 401
    return JSONResponse(content=result, status_code=status_code)


# ==================== 用户API路由 ====================
@app.get("/api/users")
async def api_users(current_user: dict = Depends(get_current_user)):
    """获取当前用户信息API"""
    user = get_user_by_id(current_user['id'])

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    formatted_user = {
        'id': user['id'],
        'user_id': user['userId'],
        'username': user['username'],
        'email': user['email'],
        'role': 'admin' if user['type'] == '管理员' else 'user',
        'created_at': user['registerDate'] + ' 00:00:00',
        'last_login_ip': user['lastLogin'],
        'is_banned': user['status'] == '封禁',
        'avatar_url': user['avatar']
    }

    return JSONResponse(content={
        'code': 200,
        'msg': 'success',
        'data': {'user': formatted_user}
    })


# ==================== 管理员API路由 ====================
@app.get("/api/admin/users")
async def api_admin_users(request: Request, current_user: dict = Depends(get_current_admin)):
    """管理员获取用户列表API"""
    users = get_all_users()

    formatted_users = []
    for user in users:
        formatted_users.append({
            'id': user['id'],
            'user_id': user['userId'],
            'username': user['username'],
            'email': user['email'],
            'role': 'admin' if user['type'] == '管理员' else 'user',
            'created_at': user['registerDate'] + ' 00:00:00',
            'last_login_ip': user['lastLogin'],
            'is_banned': user['status'] == '封禁',
            'avatar_url': user['avatar']
        })

    return JSONResponse(content={
        'code': 200,
        'msg': 'success',
        'data': {'users': formatted_users}
    })


@app.get("/api/admin/users/{user_id}")
async def api_admin_user_detail(user_id: int, current_user: dict = Depends(get_current_admin)):
    """管理员获取用户详情API"""
    user = get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    formatted_user = {
        'id': user['id'],
        'user_id': user['userId'],
        'username': user['username'],
        'email': user['email'],
        'role': 'admin' if user['type'] == '管理员' else 'user',
        'created_at': user['registerDate'] + ' 00:00:00',
        'last_login_ip': user['lastLogin'],
        'is_banned': user['status'] == '封禁',
        'avatar_url': user['avatar']
    }

    return JSONResponse(content={
        'code': 200,
        'msg': 'success',
        'data': {'user': formatted_user}
    })


@app.post("/api/admin/users")
async def api_admin_users_create(data: UserCreateRequest, current_user: dict = Depends(get_current_admin)):
    """管理员创建用户API"""
    result = register_user(data.username, data.email or '', data.password)
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


@app.put("/api/admin/users/{user_id}")
async def api_admin_user_update(user_id: int, data: UserUpdateRequest, current_user: dict = Depends(get_current_admin)):
    """管理员更新用户信息API"""
    result = update_user_info(user_id, data.username, data.email)
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


@app.post("/api/admin/users/{user_id}/ban")
async def api_admin_user_ban(user_id: int, current_user: dict = Depends(get_current_admin)):
    """管理员封禁用户API"""
    result = ban_user(user_id)
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


@app.post("/api/admin/users/{user_id}/unban")
async def api_admin_user_unban(user_id: int, current_user: dict = Depends(get_current_admin)):
    """管理员解封用户API"""
    result = unban_user(user_id)
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


@app.delete("/api/admin/users/{user_id}")
async def api_admin_user_delete(user_id: int, current_user: dict = Depends(get_current_admin)):
    """管理员删除用户API"""
    result = delete_user(user_id)
    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


@app.post("/api/create-admin")
async def api_create_admin(data: CreateAdminRequest):
    """创建管理员用户API（仅用于初始化）"""
    result = register_user(data.username, data.email or '', data.password)

    if result['code'] == 200:
        user_id = result['data']['id']
        update_result = update_user_role(user_id, 'admin')
        if update_result['code'] == 200:
            result['msg'] = '管理员用户创建成功'
            result['data']['role'] = 'admin'
        else:
            result = update_result

    status_code = 200 if result['code'] == 200 else 400
    return JSONResponse(content=result, status_code=status_code)


# ==================== 测试路由 ====================
@app.get("/test-500")
async def test_500():
    """测试500错误"""
    raise Exception("这是一个测试异常")


# ==================== 异常处理器 ====================
@app.exception_handler(404)
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


@app.exception_handler(500)
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


@app.exception_handler(422)
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


# ==================== 主程序入口 ====================
def run_server(host: str = HOST, port: int = PORT):
    """
    启动FastAPI服务器
    """
    import sys
    import io

    # 设置标准输出编码为UTF-8
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    print(f"\n🚀 {SITE_NAME} 启动成功！")
    print(f"🌐 访问地址: http://{host}:{port}")
    print(f"📁 图片目录: {os.path.abspath(IMG_ROOT_DIR)}")
    print(f"📚 API文档: http://{host}:{port}/docs")
    print(f"⚡ 核心特性：")
    print(f"  - 支持运行中新增/删除图片，实时更新")
    print(f"  - 随机接口优化：800张图片场景下响应时间<3ms")
    print(f"  - 图片直链缓存7天，随机接口禁用缓存保证随机性")
    print(f"  - 分类内图片分页：每页最多显示{CATEGORY_PAGE_SIZE}张图片")
    print(f"  - 完整跨域支持，兼容所有前端调用")
    print(f"\n⚠️  按 Ctrl+C 停止服务器")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == '__main__':
    run_server()
