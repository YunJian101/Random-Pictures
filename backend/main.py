#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI随机图API - 主应用
=========================

使用FastAPI重构的随机图片API服务
"""

import os
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from .core.config import (
    HOST, PORT, STATIC_ROOT_DIR, FRONTEND_ROOT_DIR,
    ALLOW_ORIGINS, ALLOW_METHODS, ALLOW_HEADERS
)
from .core.database import init_db, set_shutting_down
from .middlewares.logging import LoggingMiddleware
from .handlers import error_handlers

# 导入路由模块
from .routers import page, image, auth, user, admin, feedback, upload



# ==================== 初始化代码 ====================
# 确保目录存在
Path(FRONTEND_ROOT_DIR).mkdir(parents=True, exist_ok=True)
Path(STATIC_ROOT_DIR).mkdir(parents=True, exist_ok=True)

# ==================== 应用生命周期 ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    yield

    # 关闭时清理
    print("\n🔄 正在关闭服务...")
    # 设置应用正在关闭
    set_shutting_down()
    print("✅ 服务已关闭")


# ==================== 创建FastAPI应用 ====================
from fastapi import Depends
from .api.dependencies import get_current_admin
app = FastAPI(
    title="随机图API",
    description="一个高性能的随机图片API服务",
    version="3.0.0",
    lifespan=lifespan,
    docs_url=None,  # 禁用默认的文档端点
    redoc_url=None   # 禁用默认的 ReDoc 端点
)

# 添加受保护的文档路由
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi

# 受保护的 Swagger UI 文档
@app.get("/docs", dependencies=[Depends(get_current_admin)])
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title="API文档 - 管理员专用",
    )

# 受保护的 ReDoc 文档
@app.get("/redoc", dependencies=[Depends(get_current_admin)])
async def custom_redoc_html():
    return get_redoc_html(
        openapi_url="/openapi.json",
        title="API文档 - 管理员专用",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js"
    )

# 受保护的 OpenAPI JSON 端点
@app.get("/openapi.json", dependencies=[Depends(get_current_admin)])
async def get_openapi_json():
    return get_openapi(
        title="随机图API",
        version="3.0.0",
        description="一个高性能的随机图片API服务",
        routes=app.routes,
    )

# 添加CORS中间件
# 注意：当使用credentials: 'include'时，不能使用通配符*作为allow_origins
# 这里使用一个特殊的处理方式，允许所有域名的请求
from fastapi.middleware.cors import CORSMiddleware

# 检查是否需要使用通配符
if '*' in ALLOW_ORIGINS:
    # 如果配置了通配符，使用特殊处理
    @app.middleware("http")
    async def add_cors_headers(request, call_next):
        response = await call_next(request)
        origin = request.headers.get("Origin")
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = ", ".join(ALLOW_METHODS)
            response.headers["Access-Control-Allow-Headers"] = ", ".join(ALLOW_HEADERS)
        return response
else:
    # 否则使用正常的CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=ALLOW_METHODS,
        allow_headers=ALLOW_HEADERS,
    )

# 添加日志中间件
app.add_middleware(LoggingMiddleware)

# 注册异常处理器
app.add_exception_handler(404, error_handlers.not_found_handler)
app.add_exception_handler(500, error_handlers.internal_error_handler)
app.add_exception_handler(RequestValidationError, error_handlers.validation_error_handler)

# 挂载静态文件目录
if os.path.exists(STATIC_ROOT_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_ROOT_DIR), name="static")


# ==================== 注册路由 ====================
# 页面路由 - 使用HTMLResponse以正确处理响应类型
from fastapi.responses import HTMLResponse
app.get("/", response_class=HTMLResponse)(page.handle_index)
app.get("/login", response_class=HTMLResponse)(page.handle_login_page)
app.get("/admin-panel", response_class=HTMLResponse)(page.handle_admin_panel)
app.get("/user-panel", response_class=HTMLResponse)(page.handle_user_panel)
app.get("/favicon.ico")(page.handle_favicon)

# API路由 - 图片
app.get("/api/categories")(image.api_categories)  # 获取分类列表 - 所有人可使用
app.get("/api/category/images")(image.api_category_images)  # 获取指定分类的图片 - 所有人可使用
app.get("/api/images")(image.api_all_images)  # 获取所有图片列表 - 仅管理员可使用
app.get("/api/image/{image_id}")(image.api_image_detail)  # 获取单个图片详情 - 所有人可使用
app.put("/api/image/{image_id}")(image.api_update_image)  # 更新图片信息 - 仅管理员可使用
app.delete("/api/image/{image_id}")(image.api_delete_image)  # 删除图片 - 仅管理员可使用

app.get("/random")(image.handle_random_image)  # 获取随机图片 - 所有人可使用
app.get("/image")(image.handle_image)  # 获取指定图片 - 所有人可使用

# API路由 - 管理员分类管理
app.post("/api/admin/categories")(admin.api_admin_create_category)  # 创建分类 - 仅管理员可使用
app.put("/api/admin/categories/{category_id}")(admin.api_admin_update_category)  # 更新分类 - 仅管理员可使用
app.delete("/api/admin/categories/{category_id}")(admin.api_admin_delete_category)  # 删除分类 - 仅管理员可使用

# API路由 - 认证
app.post("/api/register")(auth.api_register)  # 用户注册 - 所有人可使用
app.post("/api/login")(auth.api_login)  # 用户登录 - 所有人可使用
app.post("/api/logout")(auth.api_logout)  # 用户登出 - 仅登录用户可使用
app.get("/api/auth/verify")(auth.api_auth_verify)  # 验证认证状态 - 所有人可使用

# API路由 - 用户（合并后的统一路由）
app.get("/api/users")(admin.api_admin_users)  # 获取用户列表 - 仅管理员可使用
app.get("/api/users/{user_id}")(admin.api_admin_user_detail)  # 获取用户详情 - 仅管理员可使用
app.post("/api/users")(admin.api_admin_users_create)  # 创建用户 - 仅管理员可使用
app.put("/api/users/{user_id}")(admin.api_admin_user_update)  # 更新用户 - 仅管理员可使用
app.delete("/api/users/{user_id}")(admin.api_admin_user_delete)  # 删除用户 - 仅管理员可使用
app.put("/api/users/{user_id}/ban")(admin.api_admin_user_ban)  # 封禁用户 - 仅管理员可使用
app.put("/api/users/{user_id}/unban")(admin.api_admin_user_unban)  # 解封用户 - 仅管理员可使用
app.post("/api/create-admin")(admin.api_create_admin)  # 创建管理员账号 - 仅初始设置时可使用

# API路由 - 反馈
app.get("/api/admin/feedbacks")(feedback.api_admin_feedbacks)  # 获取反馈列表 - 仅管理员可使用
app.get("/api/admin/feedbacks/{feedback_id}")(feedback.api_admin_feedback_detail)  # 获取反馈详情 - 仅管理员可使用
app.put("/api/admin/feedbacks/{feedback_id}/status")(feedback.api_admin_feedback_update_status)  # 更新反馈状态 - 仅管理员可使用
app.delete("/api/admin/feedbacks/{feedback_id}")(feedback.api_admin_feedback_delete)  # 删除反馈 - 仅管理员可使用
app.post("/api/feedbacks")(feedback.api_create_feedback)  # 创建反馈 - 所有人可使用

# API路由 - 上传
app.post("/api/admin/upload")(upload.api_upload_images)  # 上传图片 - 仅管理员可使用

# API路由 - 系统更新
app.get("/api/system/version")(admin.api_system_version)  # 获取本地版本信息 - 仅管理员可使用
app.get("/api/system/backups")(admin.api_system_backups)  # 获取备份列表 - 仅管理员可使用
app.get("/api/system/check-update")(admin.api_system_check_update)  # 检查是否有新版本 - 仅管理员可使用
app.post("/api/system/execute-update")(admin.api_system_execute_update)  # 执行完整更新流程 - 仅管理员可使用
app.post("/api/system/rollback")(admin.api_system_rollback)  # 从备份回滚 - 仅管理员可使用

# API路由 - 系统配置
app.get("/api/admin/system/config")(admin.api_admin_get_system_config)  # 获取系统配置 - 仅管理员可使用
app.put("/api/admin/system/config")(admin.api_admin_update_system_config)  # 更新系统配置 - 仅管理员可使用
app.post("/api/admin/system/config/reset")(admin.api_admin_reset_system_config)  # 重置系统配置为默认值 - 仅管理员可使用
app.get("/api/system/timezone")(admin.api_get_system_timezone)  # 获取系统时区配置 - 公共接口
app.get("/api/system/info")(admin.api_get_system_info)  # 获取系统基本信息 - 公共接口




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

    # 启动时初始化
    print(f"\n{'=' * 50}")
    print(f"🚀 随机图API 启动中...")
    print(f"{'=' * 50}")

    print(" 正在连接数据库...")

    try:
        is_new_database = init_db()
        if is_new_database:
            print("✅ 数据库不存在，已创建并初始化")
        else:
            print("✅ 数据库已存在，跳过初始化")
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")

    from .core.config import IMG_ROOT_DIR, CATEGORY_PAGE_SIZE

    print(f"\n🚀 随机图API 启动成功！")
    print(f"🌐 访问地址: http://{host}:{port}")
    print(f"📁 图片目录: {os.path.abspath(IMG_ROOT_DIR)}")
    print(f"📚 API文档: http://{host}:{port}/docs")
    print(f"⚡ 核心特性：")
    print(f"  - 支持运行中新增/删除图片，实时更新")
    print(f"  - 随机接口优化：800张图片场景下响应时间<3ms")
    print(f"  - 图片直链缓存7天，随机接口禁用缓存保证随机性")
    print(f"  - 分类内图片分页：每页最多显示{CATEGORY_PAGE_SIZE}张图片")
    print(f"  - 完整跨域支持，兼容所有前端调用")
    print(f"  - 热重载功能已启用，文件变更会自动更新")
    print(f"\n⚠️  按 Ctrl+C 停止服务器")

    import uvicorn
    uvicorn.run(
        "backend.main:app", 
        host=host, 
        port=port, 
        log_level="info",
        reload=True  # 启用热重载
    )


if __name__ == '__main__':
    run_server()

