#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
反馈路由模块
处理用户反馈相关的API请求
"""

from typing import List, Optional
from fastapi import Query, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..api.dependencies import get_current_admin, get_current_user
from ..core.database import get_async_db_connection


class FeedbackCreateRequest(BaseModel):
    """创建反馈请求"""
    content: str = Field(..., min_length=1, max_length=1000, description="反馈内容")


async def get_all_feedbacks() -> List[dict]:
    """获取所有反馈列表"""
    async with get_async_db_connection() as conn:
        feedbacks = await conn.fetch('''
            SELECT f.*, u.username
            FROM feedbacks f
            LEFT JOIN users u ON f.user_id = u.id
            ORDER BY f.created_at DESC
        ''')

    result = []
    for feedback in feedbacks:
        result.append({
            'id': feedback['id'],
            'user_id': feedback['user_id'],
            'username': feedback['username'],
            'content': feedback['content'],
            'status': feedback['status'],
            'created_at': feedback['created_at'],
            'updated_at': feedback['updated_at']
        })

    return result


async def get_feedback_by_id(feedback_id: int) -> Optional[dict]:
    """根据ID获取反馈详情"""
    async with get_async_db_connection() as conn:
        feedback = await conn.fetchrow('''
            SELECT f.*, u.username
            FROM feedbacks f
            LEFT JOIN users u ON f.user_id = u.id
            WHERE f.id = $1
        ''', feedback_id)

    if not feedback:
        return None

    return {
        'id': feedback['id'],
        'user_id': feedback['user_id'],
        'username': feedback['username'],
        'content': feedback['content'],
        'status': feedback['status'],
        'created_at': feedback['created_at'],
        'updated_at': feedback['updated_at']
    }


async def create_feedback(user_id: int, content: str) -> dict:
    """创建新反馈"""
    async with get_async_db_connection() as conn:
        feedback_id = await conn.fetchval('''
            INSERT INTO feedbacks (user_id, content)
            VALUES ($1, $2)
            RETURNING id
        ''', user_id, content)

    return await get_feedback_by_id(feedback_id)


async def update_feedback_status(feedback_id: int, status: str) -> bool:
    """更新反馈状态"""
    async with get_async_db_connection() as conn:
        result = await conn.execute('''
            UPDATE feedbacks
            SET status = $1, updated_at = CURRENT_TIMESTAMP
            WHERE id = $2
        ''', status, feedback_id)

    return result.rowcount > 0


async def delete_feedback(feedback_id: int) -> bool:
    """删除反馈"""
    async with get_async_db_connection() as conn:
        result = await conn.execute('DELETE FROM feedbacks WHERE id = $1', feedback_id)

    return result.rowcount > 0


async def api_admin_feedbacks(current_user: dict = Depends(get_current_admin)):
    """管理员获取所有反馈API"""
    feedbacks = await get_all_feedbacks()

    return JSONResponse(content={
        'code': 200,
        'msg': 'success',
        'data': {'feedbacks': feedbacks}
    })


async def api_admin_feedback_detail(feedback_id: int, current_user: dict = Depends(get_current_admin)):
    """管理员获取反馈详情API"""
    feedback = await get_feedback_by_id(feedback_id)

    if not feedback:
        raise HTTPException(status_code=404, detail="反馈不存在")

    return JSONResponse(content={
        'code': 200,
        'msg': 'success',
        'data': {'feedback': feedback}
    })


async def api_admin_feedback_update_status(
    feedback_id: int,
    status: str = Query(..., description="状态: pending, processing, resolved, closed"),
    current_user: dict = Depends(get_current_admin)
):
    """管理员更新反馈状态API"""
    valid_statuses = ['pending', 'processing', 'resolved', 'closed']
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"无效的状态值,必须是: {', '.join(valid_statuses)}")

    result = await update_feedback_status(feedback_id, status)
    if not result:
        raise HTTPException(status_code=404, detail="反馈不存在")

    return JSONResponse(content={
        'code': 200,
        'msg': '状态更新成功'
    })


async def api_admin_feedback_delete(feedback_id: int, current_user: dict = Depends(get_current_admin)):
    """管理员删除反馈API"""
    result = await delete_feedback(feedback_id)
    if not result:
        raise HTTPException(status_code=404, detail="反馈不存在")

    return JSONResponse(content={
        'code': 200,
        'msg': '删除成功'
    })


async def api_create_feedback(data: FeedbackCreateRequest, current_user: dict = Depends(get_current_user)):
    """用户创建反馈API"""
    feedback = await create_feedback(current_user['id'], data.content)

    return JSONResponse(content={
        'code': 200,
        'msg': '反馈创建成功',
        'data': {'feedback': feedback}
    })
