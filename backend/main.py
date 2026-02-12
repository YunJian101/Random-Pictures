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

from .config import (
    HOST, PORT, STATIC_ROOT_DIR, FRONTEND_ROOT_DIR,
    SITE_NAME, ALLOW_ORIGINS, ALLOW_METHODS, ALLOW_HEADERS
)
from .database import init_db
from .middlewares.logging import LoggingMiddleware
from .handlers import error_handlers

# 导入路由模块
from .routers import page, image, auth, user, admin, feedback, upload



# ==================== 应用生命周期 ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    print(f"\n{'=' * 50}")
    print(f"🚀 {SITE_NAME} 启动中...")
    print(f"{'=' * 50}")

    # 确保目录存在
    Path(FRONTEND_ROOT_DIR).mkdir(parents=True, exist_ok=True)
    Path(STATIC_ROOT_DIR).mkdir(parents=True, exist_ok=True)

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

# 注册异常处理器
app.add_exception_handler(404, error_handlers.not_found_handler)
app.add_exception_handler(500, error_handlers.internal_error_handler)
app.add_exception_handler(422, error_handlers.validation_error_handler)

# 挂载静态文件目录
if os.path.exists(STATIC_ROOT_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_ROOT_DIR), name="static")


# ==================== 注册路由 ====================
# 页面路由 - 使用HTMLResponse以正确处理响应类型
app.get("/", response_class=None)(page.handle_index)
app.get("/login", response_class=None)(page.handle_login_page)
app.get("/admin-panel", response_class=None)(page.handle_admin_panel)
app.get("/user-panel", response_class=None)(page.handle_user_panel)
app.get("/favicon.ico")(page.handle_favicon)

# API路由 - 图片
app.get("/api/categories")(image.api_categories)
app.get("/api/category/images")(image.api_category_images)
app.get("/api/images")(image.api_all_images)
app.get("/api/config")(image.api_config)
app.get("/random")(image.handle_random_image)
app.get("/image")(image.handle_image)

# API路由 - 认证
app.post("/api/register")(auth.api_register)
app.post("/api/login")(auth.api_login)
app.post("/api/logout")(auth.api_logout)
app.get("/api/auth/verify")(auth.api_auth_verify)

# API路由 - 用户
app.get("/api/users")(user.api_users)

# API路由 - 管理员
app.get("/api/admin/users")(admin.api_admin_users)
app.get("/api/admin/users/{user_id}")(admin.api_admin_user_detail)
app.post("/api/admin/users")(admin.api_admin_users_create)
app.put("/api/admin/users/{user_id}")(admin.api_admin_user_update)
app.post("/api/admin/users/{user_id}/ban")(admin.api_admin_user_ban)
app.post("/api/admin/users/{user_id}/unban")(admin.api_admin_user_unban)
app.delete("/api/admin/users/{user_id}")(admin.api_admin_user_delete)
app.post("/api/create-admin")(admin.api_create_admin)

# API路由 - 反馈
app.get("/api/admin/feedbacks")(feedback.api_admin_feedbacks)
app.get("/api/admin/feedbacks/{feedback_id}")(feedback.api_admin_feedback_detail)
app.put("/api/admin/feedbacks/{feedback_id}/status")(feedback.api_admin_feedback_update_status)
app.delete("/api/admin/feedbacks/{feedback_id}")(feedback.api_admin_feedback_delete)
app.post("/api/feedbacks")(feedback.api_create_feedback)

# API路由 - 上传（仅管理员可用）
app.post("/api/admin/upload")(upload.api_upload_images)

# 测试路由
@app.get("/test-500")
async def test_500():
    """测试500错误"""
    raise Exception("这是一个测试异常")


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

    from .config import IMG_ROOT_DIR, CATEGORY_PAGE_SIZE

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

    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == '__main__':
    run_server()

