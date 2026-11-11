#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
反馈路由模块
============

反馈现在是一段**对话线程**（feedback_messages）：
  - 用户可以提交反馈，并在自己的反馈里继续补充说明
  - 管理员可以回复，双方可多轮往来
  - 任意一方回复后，状态自动置为 `processing`（处理中），
    只有管理员显式改状态才会变成 resolved / closed

兼容保留：feedbacks.reply / replied_at 仍同步为"最后一条管理员回复"，
只读这两个字段的老调用方不会坏。

注意：所有 datetime 统一转 ISO 字符串，直接塞进 JSONResponse 会抛 TypeError。
"""

from typing import List, Optional

from fastapi import Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..api.dependencies import get_current_admin, get_current_user
from ..services.audit_service import record as audit
from ..core.database import get_async_db_connection
from ..utils.utils import execute_count


# ==================== 请求模型 ====================
class FeedbackCreateRequest(BaseModel):
    """创建反馈请求"""
    content: str = Field(..., min_length=1, max_length=1000, description="反馈内容")


class FeedbackMessageRequest(BaseModel):
    """在反馈线程里追加一条消息"""
    content: str = Field(..., min_length=1, max_length=1000, description="消息内容")


class FeedbackCloseRequest(BaseModel):
    """用户关闭自己的反馈"""
    status: str = Field('closed', description="目前只允许 closed")


class FeedbackReplyRequest(BaseModel):
    """管理员回复（保留旧接口）"""
    reply: str = Field(..., min_length=1, max_length=1000, description="回复内容")
    status: Optional[str] = Field("processing", description="回复后同时设置的状态")


VALID_STATUSES = ('pending', 'processing', 'resolved', 'closed')

# 只有这两个状态还"活着"，可以继续对话
OPEN_STATUSES = ('pending', 'processing')

# 已结束的状态：双方都不能再回复
FINISHED_STATUSES = ('resolved', 'closed')

_STATUS_LABELS = {
    'pending': '待处理',
    'processing': '处理中',
    'resolved': '已解决',
    'closed': '已关闭',
}


class ReplyNotAllowed(Exception):
    """当前状态下不允许继续回复"""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _reply_denied_reason(status: str, author: str) -> Optional[str]:
    """判断能否回复：None 表示可以，否则返回给用户看的原因

    规则：
      - 已解决 / 已关闭：双方都不能再回复
      - 待处理：只有管理员能回复（管理员回应后即进入"处理中"）
      - 处理中：双方都可以继续
    """
    if status in FINISHED_STATUSES:
        return f'该反馈{_STATUS_LABELS.get(status, status)}，无法继续回复'
    if status == 'pending' and author == 'user':
        return '问题待处理中，管理员回复后即可继续沟通'
    return None

_FEEDBACK_COLUMNS = '''
    f.id, f.user_id, f.content, f.status, f.reply, f.replied_at, f.closed_by,
    f.created_at, f.updated_at, u.username
'''

_MESSAGE_COLUMNS = 'id, feedback_id, author, author_name, content, created_at'


# ==================== 序列化工具 ====================
def _iso(value) -> Optional[str]:
    if value is None:
        return None
    try:
        return value.isoformat()
    except AttributeError:
        return str(value)


def _serialize_message(row) -> dict:
    return {
        'id': row['id'],
        'author': row['author'],
        'author_name': row['author_name'] or ('管理员' if row['author'] == 'admin' else '用户'),
        'content': row['content'],
        'created_at': _iso(row['created_at']),
    }


def _serialize(row, messages: Optional[List[dict]] = None) -> dict:
    return {
        'id': row['id'],
        'user_id': row['user_id'],
        'content': row['content'],
        'status': row['status'],
        'reply': row['reply'] if 'reply' in row.keys() else None,
        'replied_at': _iso(row['replied_at']) if 'replied_at' in row.keys() else None,
        'closed_by': row['closed_by'] if 'closed_by' in row.keys() else None,
        'created_at': _iso(row['created_at']),
        'updated_at': _iso(row['updated_at']),
        'username': row['username'] if 'username' in row.keys() else None,
        'messages': messages if messages is not None else [],
    }


# ==================== 数据访问 ====================
async def _messages_map(conn, feedback_ids: List[int]) -> dict:
    """一次取回多条反馈的全部消息，避免 N+1 查询"""
    if not feedback_ids:
        return {}

    rows = await conn.fetch(
        f'SELECT {_MESSAGE_COLUMNS} FROM feedback_messages '
        'WHERE feedback_id = ANY($1::int[]) ORDER BY created_at ASC, id ASC',
        feedback_ids,
    )

    grouped: dict = {}
    for row in rows:
        grouped.setdefault(row['feedback_id'], []).append(_serialize_message(row))
    return grouped


async def get_all_feedbacks() -> List[dict]:
    """管理员：获取全部反馈（含对话）"""
    async with get_async_db_connection() as conn:
        rows = await conn.fetch(f'''
            SELECT {_FEEDBACK_COLUMNS}
            FROM feedbacks f
            LEFT JOIN users u ON f.user_id = u.id
            ORDER BY f.created_at DESC
        ''')
        grouped = await _messages_map(conn, [row['id'] for row in rows])

    return [_serialize(row, grouped.get(row['id'], [])) for row in rows]


async def get_feedbacks_by_user(user_id: int) -> List[dict]:
    """普通用户：只返回自己的反馈（含对话）"""
    async with get_async_db_connection() as conn:
        rows = await conn.fetch(f'''
            SELECT {_FEEDBACK_COLUMNS}
            FROM feedbacks f
            LEFT JOIN users u ON f.user_id = u.id
            WHERE f.user_id = $1
            ORDER BY f.created_at DESC
        ''', user_id)
        grouped = await _messages_map(conn, [row['id'] for row in rows])

    return [_serialize(row, grouped.get(row['id'], [])) for row in rows]


async def get_feedback_by_id(feedback_id: int) -> Optional[dict]:
    """获取单条反馈（含对话）"""
    async with get_async_db_connection() as conn:
        row = await conn.fetchrow(f'''
            SELECT {_FEEDBACK_COLUMNS}
            FROM feedbacks f
            LEFT JOIN users u ON f.user_id = u.id
            WHERE f.id = $1
        ''', feedback_id)
        if not row:
            return None
        grouped = await _messages_map(conn, [feedback_id])

    return _serialize(row, grouped.get(feedback_id, []))


async def create_feedback(user_id: int, content: str) -> dict:
    """创建反馈，首条内容同时写入对话线程"""
    async with get_async_db_connection() as conn:
        feedback_id = await conn.fetchval('''
            INSERT INTO feedbacks (user_id, content)
            VALUES ($1, $2)
            RETURNING id
        ''', user_id, content)

        username = await conn.fetchval('SELECT username FROM users WHERE id = $1', user_id)
        await conn.execute('''
            INSERT INTO feedback_messages (feedback_id, user_id, author, author_name, content)
            VALUES ($1, $2, 'user', $3, $4)
        ''', feedback_id, user_id, username, content)

    return await get_feedback_by_id(feedback_id)


async def add_message(
    feedback_id: int,
    author: str,
    content: str,
    user_id: Optional[int] = None,
    author_name: Optional[str] = None,
    status: Optional[str] = None,
) -> Optional[dict]:
    """向反馈线程追加消息

    默认把状态推进到 processing（处理中）——回一句话不代表问题已解决。
    管理员可以在改状态的下拉里显式选 resolved / closed。
    """
    target_status = status or 'processing'
    if target_status not in VALID_STATUSES:
        raise ValueError(f'无效的状态值: {target_status}')

    async with get_async_db_connection() as conn:
        current = await conn.fetchrow('SELECT status FROM feedbacks WHERE id = $1', feedback_id)
        if not current:
            return None

        # 状态准入：已结束不允许回复；待处理只允许管理员回复
        denied = _reply_denied_reason(current['status'], author)
        if denied:
            raise ReplyNotAllowed(denied)

        async with conn.transaction():
            await conn.execute('''
                INSERT INTO feedback_messages (feedback_id, user_id, author, author_name, content)
                VALUES ($1, $2, $3, $4, $5)
            ''', feedback_id, user_id, author, author_name, content)

            if author == 'admin':
                # 同步老字段，保持向后兼容
                await conn.execute('''
                    UPDATE feedbacks
                    SET status = $1, reply = $2, replied_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $3
                ''', target_status, content, feedback_id)
            else:
                await conn.execute('''
                    UPDATE feedbacks
                    SET status = $1, updated_at = CURRENT_TIMESTAMP
                    WHERE id = $2
                ''', target_status, feedback_id)

    return await get_feedback_by_id(feedback_id)


async def update_feedback_status(feedback_id: int, status: str, closed_by: Optional[str] = 'admin') -> bool:
    """更新状态（管理员手动操作）

    走到 closed 时记录是谁关的；重新打开则清空 closed_by。
    """
    async with get_async_db_connection() as conn:
        affected = await execute_count(conn, '''
            UPDATE feedbacks
            SET status = $1,
                closed_by = CASE WHEN $1 = 'closed' THEN $3 ELSE NULL END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $2
        ''', status, feedback_id, closed_by or 'admin')
    return affected > 0


async def delete_feedback(feedback_id: int) -> bool:
    """删除反馈（消息由外键级联删除）"""
    async with get_async_db_connection() as conn:
        affected = await execute_count(conn, 'DELETE FROM feedbacks WHERE id = $1', feedback_id)
    return affected > 0


# ==================== 用户侧接口 ====================
async def api_create_feedback(data: FeedbackCreateRequest, current_user: dict = Depends(get_current_user)):
    """提交反馈（需登录）"""
    feedback = await create_feedback(current_user['id'], data.content)
    return JSONResponse(content={
        'code': 200,
        'msg': '反馈创建成功',
        'data': {'feedback': feedback},
    })


async def api_my_feedbacks(current_user: dict = Depends(get_current_user)):
    """查看我提交的反馈（含对话，只能看到自己的）"""
    feedbacks = await get_feedbacks_by_user(current_user['id'])
    return JSONResponse(content={
        'code': 200,
        'msg': 'success',
        'data': {'feedbacks': feedbacks, 'total': len(feedbacks)},
    })


async def api_my_feedback_message(
    feedback_id: int,
    data: FeedbackMessageRequest,
    current_user: dict = Depends(get_current_user),
):
    """用户在自己的反馈里追加说明（必须是本人）"""
    async with get_async_db_connection() as conn:
        owner_id = await conn.fetchval('SELECT user_id FROM feedbacks WHERE id = $1', feedback_id)

    if owner_id is None:
        raise HTTPException(status_code=404, detail="反馈不存在")
    if owner_id != current_user['id']:
        raise HTTPException(status_code=403, detail="只能回复自己的反馈")

    try:
        feedback = await add_message(
            feedback_id,
            author='user',
            content=data.content,
            user_id=current_user['id'],
            author_name=current_user.get('username'),
            status='processing',
        )
    except ReplyNotAllowed as denied:
        raise HTTPException(status_code=409, detail=denied.message)

    if not feedback:
        raise HTTPException(status_code=404, detail="反馈不存在")

    return JSONResponse(content={
        'code': 200,
        'msg': '已发送，问题已重新进入处理队列',
        'data': {'feedback': feedback},
    })


async def api_my_feedback_close(
    feedback_id: int,
    data: FeedbackCloseRequest,
    current_user: dict = Depends(get_current_user),
):
    """用户关闭自己的反馈（仅限待处理 / 处理中）"""
    if data.status != 'closed':
        raise HTTPException(status_code=400, detail="用户只能将反馈标记为已关闭")

    async with get_async_db_connection() as conn:
        row = await conn.fetchrow('SELECT user_id, status FROM feedbacks WHERE id = $1', feedback_id)

    if not row:
        raise HTTPException(status_code=404, detail="反馈不存在")
    if row['user_id'] != current_user['id']:
        raise HTTPException(status_code=403, detail="只能操作自己的反馈")
    if row['status'] not in OPEN_STATUSES:
        label = _STATUS_LABELS.get(row['status'], row['status'])
        raise HTTPException(status_code=409, detail=f"该反馈{label}，无法再关闭")

    await update_feedback_status(feedback_id, 'closed', closed_by='user')

    return JSONResponse(content={
        'code': 200,
        'msg': '反馈已关闭',
        'data': {'feedback': await get_feedback_by_id(feedback_id)},
    })


# ==================== 管理侧接口 ====================
async def api_admin_feedbacks(current_user: dict = Depends(get_current_admin)):
    """获取全部反馈（含对话，仅管理员）"""
    feedbacks = await get_all_feedbacks()
    return JSONResponse(content={
        'code': 200,
        'msg': 'success',
        'data': {'feedbacks': feedbacks, 'total': len(feedbacks)},
    })


async def api_admin_feedback_detail(feedback_id: int, current_user: dict = Depends(get_current_admin)):
    """获取反馈详情（仅管理员）"""
    feedback = await get_feedback_by_id(feedback_id)
    if not feedback:
        raise HTTPException(status_code=404, detail="反馈不存在")
    return JSONResponse(content={'code': 200, 'msg': 'success', 'data': {'feedback': feedback}})


async def api_admin_feedback_update_status(
    feedback_id: int,
    request: Request,
    status: str = Query(..., description="状态: pending / processing / resolved / closed"),
    current_user: dict = Depends(get_current_admin),
):
    """更新反馈状态（仅管理员）"""
    if status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"无效的状态值，必须是: {', '.join(VALID_STATUSES)}")

    if not await update_feedback_status(feedback_id, status):
        raise HTTPException(status_code=404, detail="反馈不存在")

    await audit(request, 'feedback.status', current_user,
                target_type='feedback', target_id=feedback_id,
                detail=f"反馈 #{feedback_id} 状态改为 {status}")

    return JSONResponse(content={'code': 200, 'msg': '状态更新成功'})


async def api_admin_feedback_message(
    feedback_id: int,
    data: FeedbackMessageRequest,
    request: Request,
    current_user: dict = Depends(get_current_admin),
):
    """管理员在反馈线程里回复（默认把状态置为处理中）"""
    try:
        feedback = await add_message(
            feedback_id,
            author='admin',
            content=data.content,
            user_id=current_user['id'],
            author_name=current_user.get('username'),
            status='processing',
        )
    except ReplyNotAllowed as denied:
        raise HTTPException(status_code=409, detail=denied.message)

    if not feedback:
        raise HTTPException(status_code=404, detail="反馈不存在")

    await audit(request, 'feedback.reply', current_user,
                target_type='feedback', target_id=feedback_id,
                detail=f"回复反馈 #{feedback_id}（{len(data.content)}字）")

    return JSONResponse(content={
        'code': 200,
        'msg': '回复成功',
        'data': {'feedback': feedback},
    })


async def api_admin_feedback_reply(
    feedback_id: int,
    data: FeedbackReplyRequest,
    current_user: dict = Depends(get_current_admin),
):
    """管理员回复（旧接口，内部同样写入消息线程）"""
    if data.status and data.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"无效的状态值，必须是: {', '.join(VALID_STATUSES)}")

    try:
        feedback = await add_message(
            feedback_id,
            author='admin',
            content=data.reply,
            user_id=current_user['id'],
            author_name=current_user.get('username'),
            status=data.status or 'processing',
        )
    except ReplyNotAllowed as denied:
        raise HTTPException(status_code=409, detail=denied.message)

    if not feedback:
        raise HTTPException(status_code=404, detail="反馈不存在")

    return JSONResponse(content={
        'code': 200,
        'msg': '回复成功',
        'data': {'feedback': feedback},
    })


async def api_admin_feedback_delete(feedback_id: int, request: Request, current_user: dict = Depends(get_current_admin)):
    """删除反馈（仅管理员）"""
    if not await delete_feedback(feedback_id):
        raise HTTPException(status_code=404, detail="反馈不存在")
    await audit(request, 'feedback.delete', current_user,
                target_type='feedback', target_id=feedback_id, detail=f"删除反馈 #{feedback_id}")
    return JSONResponse(content={'code': 200, 'msg': '删除成功'})
