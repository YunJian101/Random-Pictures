#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FastAPI 随机图 API - 主应用
==========================

路由在这里集中注册。权限约定：
    - 公开接口：只返回展示所需字段（分类名 / 图片数量 / 站点信息 / 版本号）
    - 登录接口：仅返回当前用户自己的数据（如"我的反馈"）
    - 管理接口：一律使用 get_current_admin，含内部字段（id / md5 / 上传 IP 等）
"""

import asyncio
import contextlib
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api.dependencies import get_current_admin, get_current_user_optional
from .core.config import (
    ALLOW_HEADERS,
    ALLOW_METHODS,
    ALLOW_ORIGINS,
    FRONTEND_ROOT_DIR,
    HOST,
    PORT,
    STATIC_ROOT_DIR,
)
from .core.database import (
    close_async_pool,
    init_async_pool,
    init_db,
    set_shutting_down,
)
from .core.tasks import cleanup_loop
from .handlers import error_handlers
from .middlewares.compression import TextCompressionMiddleware
from .middlewares.logging import LoggingMiddleware
from .middlewares.rate_limit import RateLimitMiddleware
from .routers import admin, auth, feedback, image, page, profile, sessions, upload
from .utils.utils import get_error_page


# ==================== 目录准备 ====================
Path(FRONTEND_ROOT_DIR).mkdir(parents=True, exist_ok=True)
Path(STATIC_ROOT_DIR).mkdir(parents=True, exist_ok=True)


# ==================== 应用生命周期 ====================
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🔄 正在初始化异步数据库连接池...")
    await init_async_pool()

    cleanup_task = asyncio.create_task(cleanup_loop())

    yield

    print("\n🔄 正在关闭服务...")
    set_shutting_down()
    cleanup_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await cleanup_task
    await close_async_pool()
    print("✅ 服务已关闭")


app = FastAPI(
    title="随机图API",
    description="一个自托管的随机图片 API 服务",
    # 版本号统一取 backend/__init__.py，不再手写：之前这里写死 1.1.0，
    # 结果 /docs 与 /redoc 上显示的版本一直和实际版本对不上
    version=__version__,
    lifespan=lifespan,
    docs_url=None,    # 使用下方受保护的文档路由
    redoc_url=None,
    # 关键：不传的话 FastAPI 会自动注册一个「无鉴权」的 /openapi.json，
    # 且其匹配顺序在下面手写的路由之前，等于接口定义对外全公开。
    openapi_url=None,
)


# ==================== 受保护的 API 文档 ====================
async def _guard_docs(request: Request, current_user):
    """文档页只对管理员开放

    - 未登录：浏览器会被带到登录页（而不是甩一段 {"detail":"未登录"} 的裸 JSON）
    - 非管理员：返回 403 错误页
    """
    if current_user is None:
        return RedirectResponse(url="/login", status_code=302)
    if current_user.get('role') != 'admin':
        content = await get_error_page(
            "403禁止访问",
            {"BASE_URL": str(request.base_url).rstrip("/")},
        )
        return HTMLResponse(content=content, status_code=403)
    return None


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html(request: Request, current_user: dict = Depends(get_current_user_optional)):
    denied = await _guard_docs(request, current_user)
    if denied:
        return denied
    return get_swagger_ui_html(openapi_url="/openapi.json", title="API文档 - 管理员专用")


@app.get("/redoc", include_in_schema=False)
async def custom_redoc_html(request: Request, current_user: dict = Depends(get_current_user_optional)):
    denied = await _guard_docs(request, current_user)
    if denied:
        return denied
    return get_redoc_html(
        openapi_url="/openapi.json",
        title="API文档 - 管理员专用",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@latest/bundles/redoc.standalone.js",
    )


@app.get("/openapi.json", dependencies=[Depends(get_current_admin)], include_in_schema=False)
async def get_openapi_json():
    return get_openapi(
        title="随机图API",
        version=__version__,
        description="一个自托管的随机图片 API 服务",
        routes=app.routes,
    )


# ==================== 中间件 ====================
# 允许携带凭证的跨域：不能直接使用 "*"，需要回显请求来源
if '*' in ALLOW_ORIGINS:
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=ALLOW_METHODS,
        allow_headers=ALLOW_HEADERS,
    )

# 限流：/random、/image、/thumb 按 IP 滑动窗口计数。
# 注意顺序：后添加的中间件在更外层，所以日志中间件能记录到被限流的 429 请求。
app.add_middleware(RateLimitMiddleware)

app.add_middleware(LoggingMiddleware)

# 最外层：文本类响应 gzip。图片不走这层，避免白烧 CPU（见 middlewares/compression.py）
app.add_middleware(TextCompressionMiddleware)

app.add_exception_handler(404, error_handlers.not_found_handler)
app.add_exception_handler(500, error_handlers.internal_error_handler)
app.add_exception_handler(RequestValidationError, error_handlers.validation_error_handler)

class CachedStaticFiles(StaticFiles):
    """静态资源带长缓存：JS/CSS 改版后靠文件名或部署时间自然失效即可"""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            response.headers.setdefault('cache-control', 'public, max-age=604800')
        return response


if os.path.exists(STATIC_ROOT_DIR):
    app.mount("/static", CachedStaticFiles(directory=STATIC_ROOT_DIR), name="static")


# ==================== 页面路由 ====================
app.get("/", response_class=HTMLResponse)(page.handle_index)
app.get("/login", response_class=HTMLResponse)(page.handle_login_page)
app.get("/admin-panel", response_class=HTMLResponse)(page.handle_admin_panel)
app.get("/user-panel", response_class=HTMLResponse)(page.handle_user_panel)
app.get("/favicon.ico")(page.handle_favicon)


# ==================== 公开接口（只暴露展示字段） ====================
app.get("/random")(image.handle_random_image)              # 随机图片
app.get("/image")(image.handle_image)                      # 图片直链
app.get("/thumb")(image.handle_thumb)                      # 缩略图（列表/卡片用）
app.get("/api/categories")(image.api_categories)           # 分类列表（name / description / image_count）
app.get("/api/category/images")(image.api_category_images)  # 分类下图片
app.get("/api/system/info")(admin.api_get_system_info)     # 站点名称 / 备案 / 图标
app.get("/api/system/timezone")(admin.api_get_system_timezone)
app.get("/api/system/version")(admin.api_system_version)   # 版本号（首页展示需要，去掉管理员依赖）


# ==================== 认证接口 ====================
app.post("/api/register")(auth.api_register)
app.post("/api/login")(auth.api_login)
app.post("/api/logout")(auth.api_logout)
app.get("/api/auth/verify")(auth.api_auth_verify)


# ==================== 登录用户接口（仅自己的数据） ====================
app.post("/api/feedbacks")(feedback.api_create_feedback)
app.get("/api/me")(profile.api_me)                       # 我的账号信息
app.put("/api/me")(profile.api_update_me)                # 改用户名 / 邮箱
app.put("/api/me/password")(profile.api_change_my_password)  # 改密码
app.get("/api/me/sessions")(sessions.api_my_sessions)        # 登录设备列表
app.delete("/api/me/sessions/{sid}")(sessions.api_revoke_session)  # 踢掉指定设备
app.post("/api/me/sessions/revoke-others")(sessions.api_revoke_other_sessions)
app.get("/api/my/feedbacks")(feedback.api_my_feedbacks)
app.post("/api/my/feedbacks/{feedback_id}/messages")(feedback.api_my_feedback_message)
app.put("/api/my/feedbacks/{feedback_id}/status")(feedback.api_my_feedback_close)


# ==================== 管理接口（全部要求管理员） ====================
# 总览与分类
app.get("/api/admin/stats")(admin.api_admin_stats)
app.get("/api/admin/audit-logs")(admin.api_admin_audit_logs)   # 审核日志（只读）
app.get("/api/admin/categories")(admin.api_admin_categories)
app.post("/api/admin/categories")(admin.api_admin_create_category)
app.put("/api/admin/categories/{category_id}")(admin.api_admin_update_category)
app.delete("/api/admin/categories/{category_id}")(admin.api_admin_delete_category)

# 图片
app.get("/api/images")(image.api_all_images)
app.get("/api/image/{image_id}")(image.api_image_detail)
app.put("/api/image/{image_id}")(image.api_update_image)
app.delete("/api/image/{image_id}")(image.api_delete_image)
app.post("/api/admin/upload")(upload.api_upload_images)
app.post("/api/admin/batch-action")(admin.api_admin_batch_action)

# 用户
app.get("/api/users")(admin.api_admin_users)
app.get("/api/users/{user_id}")(admin.api_admin_user_detail)
app.post("/api/users")(admin.api_admin_users_create)
app.put("/api/users/{user_id}")(admin.api_admin_user_update)
app.delete("/api/users/{user_id}")(admin.api_admin_user_delete)
app.put("/api/users/{user_id}/ban")(admin.api_admin_user_ban)
app.put("/api/users/{user_id}/unban")(admin.api_admin_user_unban)

# 反馈
app.get("/api/admin/feedbacks")(feedback.api_admin_feedbacks)
app.get("/api/admin/feedbacks/{feedback_id}")(feedback.api_admin_feedback_detail)
app.put("/api/admin/feedbacks/{feedback_id}/status")(feedback.api_admin_feedback_update_status)
app.put("/api/admin/feedbacks/{feedback_id}/reply")(feedback.api_admin_feedback_reply)
app.post("/api/admin/feedbacks/{feedback_id}/messages")(feedback.api_admin_feedback_message)
app.delete("/api/admin/feedbacks/{feedback_id}")(feedback.api_admin_feedback_delete)

# 系统配置与更新
app.get("/api/admin/system/config")(admin.api_admin_get_system_config)
app.put("/api/admin/system/config")(admin.api_admin_update_system_config)
app.put("/api/admin/system/config/batch")(admin.api_admin_update_system_config_batch)
app.post("/api/admin/system/config/reset")(admin.api_admin_reset_system_config)
app.get("/api/system/backups")(admin.api_system_backups)
app.get("/api/system/check-update")(admin.api_system_check_update)
app.post("/api/system/execute-update")(admin.api_system_execute_update)
app.post("/api/system/rollback")(admin.api_system_rollback)


# ==================== 启动入口 ====================
async def run_server(host: str = HOST, port: int = PORT):
    """启动服务

    reload 与 workers 是互斥的（reload 只能单进程），
    因此用环境变量 RELOAD 明确区分"开发热重载"和"生产多进程"。
    """
    import io
    import sys

    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', line_buffering=True)

    print(f"\n{'=' * 50}")
    print("🚀 随机图API 启动中...")
    print(f"{'=' * 50}")
    print(" 正在连接数据库...")

    try:
        is_new_database = await init_db()
        print("✅ 数据库不存在，已创建并初始化" if is_new_database else "✅ 数据库已存在，跳过初始化")
    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")

    from .core.config import CATEGORY_PAGE_SIZE, IMG_ROOT_DIR

    reload_enabled = os.getenv('RELOAD', 'false').lower() in ('1', 'true', 'yes', 'on')

    if reload_enabled:
        workers = 1
    else:
        env_workers = os.getenv('UVICORN_WORKERS')
        if env_workers and env_workers.isdigit() and int(env_workers) > 0:
            workers = int(env_workers)
        else:
            import multiprocessing
            workers = min((multiprocessing.cpu_count() or 2) * 2, 16)

    print("\n🚀 随机图API 启动成功！")
    print(f"🌐 访问地址: http://{host}:{port}")
    print(f"📁 图片目录: {os.path.abspath(IMG_ROOT_DIR)}")
    print(f"📚 API文档: http://{host}:{port}/docs （需管理员登录）")
    print("⚡ 特性："
          "\n  - 支持运行中新增/删除图片，实时更新"
          "\n  - 随机接口按「计数 + 随机偏移」定位，不做全表排序"
          "\n  - 图片直链缓存 7 天，随机接口禁用缓存"
          f"\n  - 分类内分页：每页最多 {CATEGORY_PAGE_SIZE} 张")
    print(f"\n🔧 运行模式: {'热重载（单进程）' if reload_enabled else f'{workers} 个工作进程'}")
    print("⚠️  按 Ctrl+C 停止服务器\n")

    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        log_level=os.getenv('LOG_LEVEL', 'info').lower(),
        reload=reload_enabled,
        workers=workers,
    )


if __name__ == '__main__':
    asyncio.run(run_server())
