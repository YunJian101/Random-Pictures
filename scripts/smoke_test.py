#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
接口冒烟测试
============

用标准库跑一遍关键路径，确认"部署完是好的"。不依赖 pytest，随手就能跑：

    python scripts/smoke_test.py
    BASE_URL=http://192.168.1.10:8081 python scripts/smoke_test.py
    ADMIN_USER=admin ADMIN_PASSWORD=xxx python scripts/smoke_test.py

覆盖：公开接口 / 权限边界 / 登录 / 管理接口 / 参数校验。
任一项失败 → 退出码 1，方便接到 CI 或部署脚本里。
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import http.cookiejar

BASE_URL = os.getenv('BASE_URL', 'http://127.0.0.1:8081').rstrip('/')
ADMIN_USER = os.getenv('ADMIN_USER', 'admin')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'admin123456')

GREEN, RED, YELLOW, DIM, RESET = '\033[32m', '\033[31m', '\033[33m', '\033[2m', '\033[0m'


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """不自动跟随跳转，用来断言 302"""

    def redirect_request(self, *args, **kwargs):
        return None


class Client:
    def __init__(self, follow=True):
        self.jar = http.cookiejar.CookieJar()
        handlers = [urllib.request.HTTPCookieProcessor(self.jar)]
        if not follow:
            handlers.append(NoRedirect())
        self.opener = urllib.request.build_opener(*handlers)

    def request(self, method, path, body=None, expect_status=None):
        url = BASE_URL + path
        data, headers = None, {}
        if body is not None:
            data = json.dumps(body).encode('utf-8')
            headers['Content-Type'] = 'application/json'

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            resp = self.opener.open(req, timeout=20)
            status, raw = resp.status, resp.read()
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
        except urllib.error.HTTPError as e:
            status, raw = e.code, e.read()
            hdrs = {k.lower(): v for k, v in (e.headers or {}).items()}
        except Exception as e:
            return 0, None, str(e).encode()

        payload = None
        if raw and 'json' in hdrs.get('content-type', ''):
            try:
                payload = json.loads(raw)
            except Exception:
                payload = None
        return status, payload, raw


results = []


def check(name, condition, detail=''):
    results.append((name, bool(condition), detail))
    mark = f'{GREEN}✓{RESET}' if condition else f'{RED}✗{RESET}'
    print(f'  {mark} {name}' + (f'  {DIM}{detail}{RESET}' if detail else ''))
    return condition


def main():
    print(f'\n接口冒烟测试 · {BASE_URL}\n')

    anon = Client()
    no_redirect = Client(follow=False)
    admin = Client()

    print(f'{YELLOW}[1] 页面与公开接口{RESET}')
    status, _, raw = anon.request('GET', '/')
    check('首页 200', status == 200, f'HTTP {status}')
    check('首页返回 HTML', b'<!DOCTYPE html' in raw[:200])

    status, _, _ = anon.request('GET', '/login')
    check('登录页 200', status == 200, f'HTTP {status}')

    status, data, _ = anon.request('GET', '/api/system/info')
    check('站点信息 200', status == 200 and data and data.get('code') == 200)

    status, data, _ = anon.request('GET', '/api/system/version')
    check('版本号 200', status == 200 and data and data.get('code') == 200)

    print(f'{YELLOW}[2] 权限边界（不该给的数据给不到）{RESET}')
    status, data, _ = anon.request('GET', '/api/categories')
    cats = (data or {}).get('category_list') or []
    leaked = bool(cats) and ('id' in cats[0] or 'status' in cats[0])
    check('分类公开接口不泄露 id/status', status == 200 and not leaked,
          '含内部字段' if leaked else f'{len(cats)} 个分类')

    status, _, _ = anon.request('GET', '/openapi.json')
    check('匿名读 openapi.json → 401', status == 401, f'HTTP {status}')

    status, _, _ = no_redirect.request('GET', '/docs')
    check('匿名访问 /docs → 302 跳登录', status == 302, f'HTTP {status}')

    for path, label in [('/api/me', '我的资料'), ('/api/admin/stats', '统计'),
                        ('/api/admin/categories', '分类管理'), ('/api/users', '用户列表'),
                        ('/api/images', '图片列表')]:
        status, _, _ = anon.request('GET', path)
        check(f'匿名访问{label} → 401', status == 401, f'HTTP {status}')

    status, _, _ = anon.request('POST', '/api/feedbacks', {'content': '匿名提交'})
    check('匿名提交反馈 → 401', status == 401, f'HTTP {status}')

    print(f'{YELLOW}[3] 图片接口{RESET}')
    status, _, raw = anon.request('GET', '/random')
    is_image = raw.startswith((b'\x89PNG', b'\xff\xd8\xff', b'GIF8', b'RIFF'))
    check('/random 返回图片流', status == 200 and is_image, f'HTTP {status}, {len(raw)}B')

    status, data, _ = anon.request('GET', '/random?format=exe')
    check('非法 format → 422', status == 422, f'HTTP {status}')

    status, data, _ = anon.request('GET', '/random?exclude=abc')
    check('非法 exclude → 422', status == 422, f'HTTP {status}')

    status, _, _ = anon.request('GET', '/image?path=' + urllib.parse.quote('../../etc/passwd'))
    check('路径穿越被拦 → 422', status == 422, f'HTTP {status}')

    print(f'{YELLOW}[4] 登录与会话{RESET}')
    status, _, _ = anon.request('POST', '/api/login', {'account': ADMIN_USER, 'password': 'definitely-wrong'})
    check('错误密码 → 401', status == 401, f'HTTP {status}')

    status, data, _ = admin.request('POST', '/api/login',
                                    {'account': ADMIN_USER, 'password': ADMIN_PASSWORD})
    check('管理员登录 200', status == 200 and (data or {}).get('code') == 200, f'HTTP {status}')

    status, data, _ = admin.request('GET', '/api/auth/verify')
    check('会话校验 200', status == 200 and data and data.get('code') == 200)

    status, data, _ = admin.request('GET', '/api/me')
    user = ((data or {}).get('data') or {}).get('user') or {}
    check('读取我的资料', status == 200 and bool(user.get('username')),
          f"{user.get('username')} / {user.get('role')}")

    print(f'{YELLOW}[5] 管理接口{RESET}')
    status, data, _ = admin.request('GET', '/api/admin/stats')
    stats = ((data or {}).get('data') or {})
    check('统计接口', status == 200 and 'images' in stats,
          f"图片 {stats.get('images', {}).get('total')} / 分类 {stats.get('categories', {}).get('total')}")

    status, data, _ = admin.request('GET', '/api/admin/categories')
    check('分类管理接口', status == 200 and (data or {}).get('code') == 200)

    status, data, _ = admin.request('GET', '/api/images?sort=size_desc&page=1')
    check('图片列表 + 排序', status == 200 and data and data.get('sort') == 'size_desc',
          f"sort={data.get('sort') if data else '?'}")

    status, data, _ = admin.request('GET', '/api/images?sort=DROP%20TABLE')
    check('非法排序回落到默认', status == 200 and data and data.get('sort') == 'created_desc',
          f"sort={data.get('sort') if data else '?'}")

    status, data, _ = admin.request('GET', '/api/users')
    check('用户列表', status == 200 and (data or {}).get('code') == 200)

    status, data, _ = admin.request('GET', '/api/admin/feedbacks')
    check('反馈列表', status == 200 and (data or {}).get('code') == 200)

    status, data, _ = admin.request('GET', '/api/admin/system/config')
    check('系统配置', status == 200 and (data or {}).get('code') == 200)

    # 审核日志：列表 / 动作筛选 / 日期区间（日期参数曾因类型不匹配 500）
    status, data, _ = admin.request('GET', '/api/admin/audit-logs?page=1&page_size=5')
    check('审核日志列表', status == 200 and (data or {}).get('code') == 200)

    status, data, _ = admin.request(
        'GET', '/api/admin/audit-logs?start=2020-01-01&end=2999-12-31'
    )
    check('审核日志日期区间', status == 200 and (data or {}).get('code') == 200)

    status, data, _ = admin.request('GET', '/api/admin/audit-logs?action=security.denied')
    check('审核日志动作筛选', status == 200 and (data or {}).get('code') == 200)

    status, _, _ = admin.request('GET', '/docs')
    check('管理员可看 /docs', status == 200, f'HTTP {status}')

    status, _, _ = admin.request('GET', '/openapi.json')
    check('管理员可读 openapi.json', status == 200, f'HTTP {status}')

    # 退出登录后再验证会话确实失效
    status, _, _ = admin.request('POST', '/api/logout')
    check('退出登录 200', status == 200, f'HTTP {status}')
    status, _, _ = admin.request('GET', '/api/me')
    check('退出后 /api/me → 401', status == 401, f'HTTP {status}')

    # ---------- 汇总 ----------
    total = len(results)
    passed = sum(1 for _, ok, _ in results if ok)
    failed = total - passed

    print(f'\n{"-" * 52}')
    if failed:
        print(f'{RED}✗ {failed} 项失败{RESET} / 共 {total} 项\n')
        for name, ok, detail in results:
            if not ok:
                print(f'  {RED}失败{RESET}: {name}  {detail}')
        return 1

    print(f'{GREEN}✓ 全部 {total} 项通过{RESET}\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
