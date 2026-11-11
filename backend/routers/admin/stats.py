#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理接口 · stats
============

数据总览：图片、分类、用户、反馈的汇总指标
"""

from fastapi import Depends
from fastapi.responses import JSONResponse
from ...api.dependencies import get_current_admin

async def api_admin_stats(current_user: dict = Depends(get_current_admin)):
    """后台总览统计（仅管理员）

    把原先分散在 4 个列表接口里的数字收敛成一个轻量接口，
    前端首屏只发一个请求即可渲染 KPI。
    """
    from ...core.database import get_async_db_connection

    try:
        async with get_async_db_connection() as conn:
            image_total = await conn.fetchval("SELECT COUNT(*) FROM images WHERE status = 'enabled'")
            image_size = await conn.fetchval('SELECT COALESCE(SUM(file_size), 0) FROM images')
            image_week = await conn.fetchval(
                "SELECT COUNT(*) FROM images WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'"
            )
            category_total = await conn.fetchval("SELECT COUNT(*) FROM categories WHERE status = 'enabled'")
            user_total = await conn.fetchval('SELECT COUNT(*) FROM users')
            user_banned = await conn.fetchval("SELECT COUNT(*) FROM users WHERE status = 'banned'")
            feedback_pending = await conn.fetchval("SELECT COUNT(*) FROM feedbacks WHERE status = 'pending'")
            feedback_total = await conn.fetchval('SELECT COUNT(*) FROM feedbacks')
            view_total = await conn.fetchval('SELECT COALESCE(SUM(view_count), 0) FROM images')
            # 近 24 小时的安全事件（越权/限流/非法请求/5xx），供总览页展示
            security_24h = await conn.fetchval('''
                SELECT COUNT(*) FROM audit_logs
                WHERE action LIKE 'security.%'
                  AND created_at >= CURRENT_TIMESTAMP - INTERVAL '24 hours'
            ''')
            security_latest = await conn.fetchval('''
                SELECT MAX(created_at) FROM audit_logs WHERE action LIKE 'security.%'
            ''')

        image_total = int(image_total or 0)
        return JSONResponse(content={
            'code': 200,
            'msg': 'success',
            'data': {
                'images': {
                    'total': image_total,
                    'total_size': int(image_size or 0),
                    'new_last_7d': int(image_week or 0),
                    'views': int(view_total or 0),
                },
                'categories': {'total': int(category_total or 0)},
                'users': {'total': int(user_total or 0), 'banned': int(user_banned or 0)},
                'feedbacks': {'total': int(feedback_total or 0), 'pending': int(feedback_pending or 0)},
                'security': {
                    'last_24h': int(security_24h or 0),
                    'latest_at': security_latest.isoformat() if security_latest else '',
                },
            },
        })
    except Exception as e:
        print(f"[ERROR] 获取统计数据失败: {str(e)}")
        return JSONResponse(content={'code': 500, 'msg': '获取统计数据失败'}, status_code=500)


# ==================== 管理端：批量更新系统配置 ====================
