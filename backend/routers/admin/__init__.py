#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理接口包
==========

原来 routers/admin.py 是一个 1300 多行的混合文件（用户、分类、图片批处理、
统计、系统更新、系统配置全在里面），改一处要在一堆无关代码里翻。现按业务域拆开：

    users.py       账号管理
    categories.py  分类管理
    images.py      图片批量操作
    stats.py       数据总览
    system.py      系统信息与版本更新
    config.py      系统配置读写

main.py 仍然通过 `from .routers import admin` + `admin.api_xxx` 注册路由，
URL 和权限依赖与拆分前完全一致。新代码请直接 import 具体子模块。
"""

from .audit import api_admin_audit_logs  # noqa: F401
from .categories import (  # noqa: F401
    api_admin_categories,
    api_admin_create_category,
    api_admin_delete_category,
    api_admin_update_category,
)
from .config import (  # noqa: F401
    api_admin_get_system_config,
    api_admin_reset_system_config,
    api_admin_update_system_config,
    api_admin_update_system_config_batch,
    validate_config_value,
)
from .images import api_admin_batch_action  # noqa: F401
from .stats import api_admin_stats  # noqa: F401
from .system import (  # noqa: F401
    api_get_system_info,
    api_get_system_timezone,
    api_system_backups,
    api_system_check_update,
    api_system_execute_update,
    api_system_rollback,
    api_system_version,
)
from .users import (  # noqa: F401
    api_admin_user_ban,
    api_admin_user_delete,
    api_admin_user_detail,
    api_admin_user_unban,
    api_admin_user_update,
    api_admin_users,
    api_admin_users_create,
)

__all__ = [
    'api_admin_users',
    'api_admin_user_detail',
    'api_admin_users_create',
    'api_admin_user_update',
    'api_admin_user_ban',
    'api_admin_user_unban',
    'api_admin_user_delete',
    'api_admin_categories',
    'api_admin_create_category',
    'api_admin_update_category',
    'api_admin_delete_category',
    'api_admin_batch_action',
    'api_admin_stats',
    'api_system_backups',
    'api_system_version',
    'api_system_check_update',
    'api_system_execute_update',
    'api_system_rollback',
    'api_get_system_timezone',
    'api_get_system_info',
    'api_admin_get_system_config',
    'api_admin_update_system_config',
    'api_admin_update_system_config_batch',
    'api_admin_reset_system_config',
    'validate_config_value',
    'api_admin_audit_logs',
]
