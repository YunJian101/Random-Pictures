#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理接口 · config
=============

系统配置读写：单条 / 批量更新、重置，以及配置项校验
"""

from fastapi import (
    Depends,
    Request,
)
from fastapi.responses import JSONResponse
from ...api.dependencies import get_current_admin

from ...core import runtime_config
from ...services.audit_service import record as audit
from .system import invalidate_config_cache

# 运行时数值配置的合法区间（键 → (最小, 最大)）
# 下限不能是 0：限流阈值 0 等于「全部拒绝」，锁定次数 0 会让任何人一登录就被锁
INT_RULES: dict[str, tuple[int, int]] = {
    'rate_limit_per_minute': (1, 10000),
    'rate_limit_auth_per_minute': (1, 1000),
    'login_max_failures': (1, 50),
    'login_ip_max_failures': (1, 500),
    'login_lock_base_seconds': (5, 3600),
    'login_lock_max_seconds': (30, 86400),
    'max_sessions_per_user': (1, 100),
    'session_cleanup_interval': (60, 86400),
    'audit_retention_days': (7, 3650),
    'max_upload_mb': (1, 100),
    'register_max_per_window': (1, 100),
    'register_window_seconds': (60, 86400),
    'register_min_interval_seconds': (0, 3600),
}


def _invalidate_all() -> None:
    """配置变更后同时失效两份缓存：站点信息缓存 + 运行时配置快照"""
    invalidate_config_cache()
    runtime_config.invalidate()


BOOL_CONFIG_KEYS = (
    'enable_access_log',
    'show_beian_info',
    'enable_path_traversal_protection',
    'enable_hotlink_protection',
    'enable_ip_blacklist',
    'enable_rate_limit',
    'enable_login_guard',
    'enable_register_guard',
    'trust_proxy',
)


async def api_admin_get_system_config(current_user: dict = Depends(get_current_admin)):
    """管理员获取系统配置API"""
    from ...core.database import get_async_db_connection

    try:
        async with get_async_db_connection() as conn:
            # 查询所有系统配置
            configs = await conn.fetch('SELECT config_key, config_value, description FROM system_configs')

            # 构建配置字典
            config_dict = {}
            for config in configs:
                config_dict[config['config_key']] = {
                    'value': config['config_value'],
                    'description': config['description']
                }

            return JSONResponse(content={
                'code': 200,
                'msg': '获取系统配置成功',
                'data': config_dict
            })
    except Exception as e:
        print(f"[ERROR] 获取系统配置时发生错误: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': '获取系统配置时发生错误'
        }, status_code=500)


def validate_config_value(config_key: str, config_value: str) -> tuple[bool, str]:
    """
    验证配置值的有效性
    
    Args:
        config_key: 配置键
        config_value: 配置值
        
    Returns:
        (is_valid, error_message): 验证结果和错误信息
    """
    # 通用验证：配置值不能为空
    if config_value is None:
        return False, "配置值不能为空"
    
    # 转换为字符串
    config_value = str(config_value)
    
    # 导入工具函数
    from ...utils.utils import validate_local_path, is_remote_url
    
    # 根据配置键进行特定验证
    if config_key == 'site_name':
        if len(config_value) == 0:
            return False, "站点名称不能为空"
        if len(config_value) > 50:
            return False, "站点名称长度不能超过50个字符"
    elif config_key == 'site_domain':
        if config_value:
            if not is_remote_url(config_value):
                return False, "站点域名必须是有效的URL格式"
    elif config_key == 'favicon_url':
        if config_value:
            # 检查是否为URL
            if not is_remote_url(config_value):
                # 本地路径验证
                is_valid, error_msg = validate_local_path(config_value)
                if not is_valid:
                    return False, error_msg
                # 确保路径是相对路径，不包含绝对路径标志
                if config_value.startswith('/'):
                    # 允许以/开头的路径，但会在处理时转换为相对路径
                    pass
    elif config_key == 'icp_beian':
        if len(config_value) > 50:
            return False, "ICP备案号长度不能超过50个字符"
    elif config_key == 'beian_link':
        if config_value:
            if not is_remote_url(config_value):
                return False, "备案信息链接必须是有效的URL格式"
    elif config_key == 'site_launch_date':
        # 允许留空（首页就不显示「稳定交付 N 天」）；有值必须是 YYYY-MM-DD 的真实日期
        if config_value:
            import re
            from datetime import date
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', config_value):
                return False, "项目创建日期格式应为 YYYY-MM-DD"
            try:
                date.fromisoformat(config_value)
            except ValueError:
                return False, "项目创建日期不是有效的日期"
    elif config_key == 'timezone':
        if not config_value:
            return False, "时区设置不能为空"
        # 简化时区验证，避免依赖pytz模块
        # 只验证基本格式，不进行完整的时区名称验证
        import re
        timezone_pattern = r'^[A-Za-z_]+/[A-Za-z_]+$'
        if not re.match(timezone_pattern, config_value):
            return False, "请输入有效的时区名称格式，如 Asia/Shanghai"
    elif config_key in BOOL_CONFIG_KEYS:
        if config_value not in ['true', 'false']:
            return False, "该配置必须设置为 'true' 或 'false'"
    elif config_key in INT_RULES:
        low, high = INT_RULES[config_key]
        try:
            number = int(str(config_value).strip())
        except (TypeError, ValueError):
            return False, "该配置必须是整数"
        if not (low <= number <= high):
            return False, f"该配置的取值范围是 {low} ~ {high}"

    return True, ""

async def api_admin_update_system_config(request: Request, current_user: dict = Depends(get_current_admin)):
    """管理员更新系统配置API"""
    from ...core.database import get_async_db_connection

    try:
        data = await request.json()
        config_key = data.get('key')
        config_value = data.get('value')

        if not config_key:
            return JSONResponse(content={
                'code': 400,
                'msg': '配置键不能为空'
            }, status_code=400)

        # 验证配置值
        is_valid, error_msg = validate_config_value(config_key, config_value)
        if not is_valid:
            return JSONResponse(content={
                'code': 400,
                'msg': error_msg
            }, status_code=400)

        async with get_async_db_connection() as conn:
            # 检查配置是否存在
            existing = await conn.fetchrow('SELECT id FROM system_configs WHERE config_key = $1', config_key)
            if not existing:
                return JSONResponse(content={
                    'code': 404,
                    'msg': '配置不存在'
                }, status_code=404)

            # 更新配置
            await conn.execute('''
                UPDATE system_configs 
                SET config_value = $1, updated_at = CURRENT_TIMESTAMP 
                WHERE config_key = $2
            ''', config_value, config_key)

            # 清除缓存，确保下次获取系统信息时从数据库读取最新值
            _invalidate_all()

            await audit(request, 'config.update', current_user,
                        target_type='config', target_id=config_key,
                        detail=f"修改配置 {config_key} = {config_value}")

            return JSONResponse(content={
                'code': 200,
                'msg': '配置更新成功'
            })
    except Exception as e:
        print(f"[ERROR] 更新系统配置时发生错误: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': '更新系统配置时发生错误'
        }, status_code=500)


async def api_admin_reset_system_config(request: Request, current_user: dict = Depends(get_current_admin)):
    """管理员重置系统配置为默认值API"""
    from ...core.database import get_async_db_connection

    try:
        async with get_async_db_connection() as conn:
            # 重置所有配置为默认值（将 default_value 复制到 config_value）
            await conn.execute('''
                UPDATE system_configs 
                SET config_value = default_value, updated_at = CURRENT_TIMESTAMP
            ''')

            # 清除缓存，确保下次获取系统信息时从数据库读取最新值
            _invalidate_all()

            await audit(request, 'config.reset', current_user,
                        target_type='config', detail='把所有系统配置恢复为默认值')

            return JSONResponse(content={
                'code': 200,
                'msg': '系统配置已重置为默认值'
            })
    except Exception as e:
        print(f"[ERROR] 重置系统配置时发生错误: {str(e)}")
        return JSONResponse(content={
            'code': 500,
            'msg': '重置系统配置时发生错误'
        }, status_code=500)



async def api_admin_update_system_config_batch(request: Request, current_user: dict = Depends(get_current_admin)):
    """批量更新系统配置（仅管理员）

    原接口一次只能改一个 key，保存设置页要发 8~10 个请求；
    这里提供批量版本，一次性校验 + 一次性提交。
    """
    from ...core.database import get_async_db_connection

    try:
        data = await request.json()
        items = data.get('items') or {}
        if not isinstance(items, dict) or not items:
            return JSONResponse(content={'code': 400, 'msg': '没有需要更新的配置项'}, status_code=400)

        # 先全部校验，避免部分写入
        for key, value in items.items():
            is_valid, error_msg = validate_config_value(key, str(value))
            if not is_valid:
                return JSONResponse(content={'code': 400, 'msg': f'{key}: {error_msg}'}, status_code=400)

        async with get_async_db_connection() as conn:
            async with conn.transaction():
                for key, value in items.items():
                    updated = await conn.fetchval('''
                        UPDATE system_configs
                        SET config_value = $1, updated_at = CURRENT_TIMESTAMP
                        WHERE config_key = $2
                        RETURNING id
                    ''', str(value), key)
                    if updated is None:
                        return JSONResponse(
                            content={'code': 404, 'msg': f'配置项不存在: {key}'}, status_code=404
                        )

        _invalidate_all()

        await audit(request, 'config.update', current_user,
                    target_type='config',
                    target_id=','.join(list(items.keys())[:10]),
                    detail=f"批量修改 {len(items)} 项配置",
                    metadata={'items': {k: str(v) for k, v in items.items()}})

        return JSONResponse(content={
            'code': 200,
            'msg': '配置更新成功',
            'data': {'updated': len(items)},
        })
    except Exception as e:
        print(f"[ERROR] 批量更新系统配置失败: {str(e)}")
        return JSONResponse(content={'code': 500, 'msg': '更新系统配置时发生错误'}, status_code=500)
