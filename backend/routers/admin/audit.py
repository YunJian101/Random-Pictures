#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理接口 · audit
=============

审核日志查询（只读）。日志的写入由各业务接口调用 services/audit_service.py 完成，
这里不提供任何修改/删除单条日志的入口——审计记录能被编辑就失去意义了。
"""

from fastapi import (
    Depends,
    Query,
    Request,
)
from fastapi.responses import JSONResponse

from ...api.dependencies import get_current_admin


async def api_admin_audit_logs(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    action: str = Query(''),
    keyword: str = Query(''),
    start: str = Query(''),
    end: str = Query(''),
    current_user: dict = Depends(get_current_admin),
):
    """审核日志分页查询

    支持按动作码、关键字（操作人 / 详情 / 对象 ID）、日期区间筛选。
    返回里带上各动作的实际条数，前端下拉可以直接显示「登录 (128)」。
    """
    from ...services.audit_service import list_logs

    data = await list_logs(
        page=page,
        page_size=page_size,
        action=action,
        keyword=keyword,
        start=start,
        end=end,
    )

    if data.get('error'):
        return JSONResponse(
            content={'code': 500, 'msg': f'查询审核日志失败: {data["error"]}'},
            status_code=500,
        )

    return JSONResponse(content={'code': 200, 'msg': '获取审核日志成功', 'data': data})
