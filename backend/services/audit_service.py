#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
审核日志
========

记录「谁在什么时候对什么做了什么」，用于事后追溯。和管理后台的反馈、用户操作不同，
这里写进去的行不允许修改（只读 + 到期清理），否则审计就没有意义了。

设计取舍：
- **写日志永远不影响业务**：任何异常只打一行告警，不会让删除/封禁这类操作失败；
- **冗余存用户名**：用户被删掉之后，日志里仍然看得到当时是谁操作的；
- **动作码用 `域.动作`**：如 `user.ban`、`config.update`，便于按前缀筛选；
- **metadata 存结构化信息**：JSONB，比如改动前后的值、批量操作的数量。

清理策略见 core/tasks.py：默认保留 90 天，可在管理后台「系统设置」里改。
"""

import json
from datetime import datetime
from typing import Optional

from ..core.database import get_async_db_connection
from ..utils.request import client_ip
from ..utils.utils import execute_count

__all__ = [
    'ACTION_LABELS',
    'record',
    'list_logs',
    'cleanup_logs',
]

# 动作码 → 中文名。新增动作时在这里登记，后台筛选下拉会自动带上
ACTION_LABELS: dict[str, str] = {
    'auth.login': '登录',
    'auth.logout': '登出',
    'session.revoke': '退出登录设备',
    'user.create': '新建用户',
    'user.update': '修改用户',
    'user.ban': '封禁用户',
    'user.unban': '解封用户',
    'user.delete': '删除用户',
    'category.create': '新建分类',
    'category.update': '修改分类',
    'category.delete': '删除分类',
    'image.update': '修改图片',
    'image.delete': '删除图片',
    'image.batch': '批量操作图片',
    'upload.images': '上传图片',
    'feedback.reply': '回复反馈',
    'feedback.status': '变更反馈状态',
    'feedback.delete': '删除反馈',
    'config.update': '修改系统配置',
    'config.reset': '重置系统配置',
    'system.update': '执行版本更新',
    'system.rollback': '版本回滚',
    # 异常请求（由 middlewares/security_events.py 写入）
    'security.denied': '未授权/越权访问',
    'security.rate_limit': '触发限流',
    'security.rejected': '非法请求',
    'security.server_error': '服务端错误',
}


def _actor_fields(actor: Optional[dict]) -> tuple:
    """从 current_user 里取操作人信息（匿名/系统操作留空）"""
    if not actor:
        return (None, '系统', None)
    return (
        actor.get('id'),
        actor.get('username') or '未知用户',
        actor.get('role'),
    )


async def record(
    request=None,
    action: str = '',
    actor: Optional[dict] = None,
    target_type: Optional[str] = None,
    target_id=None,
    detail: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> None:
    """写一条审核日志（永不抛异常）

    参数:
        request: 用于取 IP / UA，可以传 None（后台任务等无请求场景）
        action: 动作码，建议用 ACTION_LABELS 里登记的键
        actor: 当前用户 dict（含 id / username / role）
        target_type / target_id: 被操作对象的类型与标识
        detail: 给人看的一句话，例如「封禁用户 text01，原因：刷接口」
        metadata: 结构化附加信息，如 {'before': {...}, 'after': {...}}
    """
    try:
        actor_id, actor_name, actor_role = _actor_fields(actor)

        ip = None
        user_agent = None
        if request is not None:
            try:
                ip = await client_ip(request)
                user_agent = (request.headers.get('user-agent') or '')[:200]
            except Exception:
                pass

        # asyncpg 不会自动把 dict 编码成 jsonb，这里显式序列化 + 类型转换
        metadata_param = json.dumps(metadata, ensure_ascii=False) if metadata else None

        async with get_async_db_connection() as conn:
            await conn.execute('''
                INSERT INTO audit_logs
                    (actor_id, actor_name, actor_role, action, target_type, target_id,
                     detail, metadata, ip, user_agent)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10)
            ''', actor_id, actor_name, actor_role, action,
                target_type, None if target_id is None else str(target_id),
                detail, metadata_param, ip, user_agent)

    except Exception as e:
        # 审计失败不能连累业务
        print(f"[WARN] 写审核日志失败({action}): {str(e)}")


def _parse_date(value: str):
    """把 YYYY-MM-DD 解析成 date；空值或格式不对返回 None"""
    if not value:
        return None
    try:
        return datetime.strptime(str(value).strip(), '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


async def list_logs(
    page: int = 1,
    page_size: int = 20,
    action: str = '',
    keyword: str = '',
    start: str = '',
    end: str = '',
) -> dict:
    """分页查询审核日志

    筛选条件全部可选：动作码、关键字（操作人/详情/对象）、时间区间（YYYY-MM-DD）。
    """
    page = max(1, int(page or 1))
    page_size = min(200, max(1, int(page_size or 20)))

    where = []
    params: list = []

    if action:
        params.append(action)
        where.append(f'action = ${len(params)}')

    if keyword:
        params.append(f'%{keyword.strip()}%')
        idx = len(params)
        where.append(
            f'(actor_name ILIKE ${idx} OR detail ILIKE ${idx} OR target_id ILIKE ${idx})'
        )

    # 日期参数必须传 date 对象：asyncpg 会按 SQL 里的 ::date 推断参数类型，
    # 传字符串会报 "expected date, got str"（表现为 500）。非法值直接忽略该条件。
    start_date = _parse_date(start)
    if start_date:
        params.append(start_date)
        where.append(f'created_at >= ${len(params)}::date')

    end_date = _parse_date(end)
    if end_date:
        # 结束日期包含当天：< 次日 0 点
        params.append(end_date)
        where.append(f'created_at < (${len(params)}::date + INTERVAL \'1 day\')')

    where_sql = ('WHERE ' + ' AND '.join(where)) if where else ''

    try:
        async with get_async_db_connection() as conn:
            total = await conn.fetchval(
                f'SELECT COUNT(*) FROM audit_logs {where_sql}', *params
            )

            rows = await conn.fetch(
                f'''
                SELECT id, actor_id, actor_name, actor_role, action, target_type,
                       target_id, detail, metadata, ip, created_at
                FROM audit_logs
                {where_sql}
                ORDER BY created_at DESC, id DESC
                LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
                ''',
                *params, page_size, (page - 1) * page_size,
            )

            # 各动作的实际条数，供前端下拉显示「登录 (128)」
            counts = await conn.fetch(
                'SELECT action, COUNT(*) AS n FROM audit_logs GROUP BY action ORDER BY n DESC'
            )

        items = []
        for row in rows:
            # asyncpg 把 jsonb 当字符串返回（没注册编解码器），这里解析成对象给前端
            meta = row['metadata']
            if isinstance(meta, str) and meta:
                try:
                    meta = json.loads(meta)
                except ValueError:
                    pass

            items.append({
                'id': row['id'],
                'actor_id': row['actor_id'],
                'actor_name': row['actor_name'],
                'actor_role': row['actor_role'],
                'action': row['action'],
                'action_label': ACTION_LABELS.get(row['action'], row['action']),
                'target_type': row['target_type'],
                'target_id': row['target_id'],
                'detail': row['detail'] or '',
                'metadata': meta,
                'ip': row['ip'] or '',
                'created_at': row['created_at'].isoformat() if row['created_at'] else '',
            })

        return {
            'items': items,
            'total': total or 0,
            'page': page,
            'page_size': page_size,
            'total_pages': max(1, -(-(total or 0) // page_size)),
            'actions': [
                {
                    'value': row['action'],
                    'label': ACTION_LABELS.get(row['action'], row['action']),
                    'count': row['n'],
                }
                for row in counts
            ],
        }

    except Exception as e:
        print(f"[ERROR] 查询审核日志失败: {str(e)}")
        return {
            'items': [], 'total': 0, 'page': page, 'page_size': page_size,
            'total_pages': 1, 'actions': [], 'error': str(e),
        }


async def cleanup_logs(retention_days: int) -> int:
    """删除超过保留期的日志"""
    try:
        days = max(1, int(retention_days))
        async with get_async_db_connection() as conn:
            return await execute_count(conn, '''
                DELETE FROM audit_logs
                WHERE created_at < CURRENT_TIMESTAMP - make_interval(days => $1)
            ''', days)
    except Exception as e:
        print(f"[WARN] 清理审核日志失败: {str(e)}")
        return 0
