# 配置说明

配置分两层：

1. **环境变量**：部署时确定，改动需重启容器；同时作为运行时配置的**出厂默认值**。
2. **运行时配置**：存在数据库 `system_configs` 表，可在管理后台「系统设置」修改，保存后约 5 秒对所有进程生效，**无需重启**。

优先级：运行时配置（数据库）> 环境变量 > 代码默认值。

---

## 环境变量

在项目根目录的 `.env` 中设置，示例见 `.env.example`。

### 服务

| 变量 | 默认 | 说明 |
|---|---|---|
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8081` | 监听端口 |
| `APP_PORT` | `8081` | 宿主机映射端口（仅 docker-compose 使用） |
| `UVICORN_WORKERS` | 2 | 工作进程数；`RELOAD=true` 时强制为 1 |
| `RELOAD` | `false` | 开发热重载 |
| `LOG_LEVEL` | `info` | 日志级别 |
| `TZ` | `Asia/Shanghai` | 容器时区 |

### 数据库

| 变量 | 默认 | 说明 |
|---|---|---|
| `DATABASE_URL` | 由 compose 注入 | PostgreSQL 连接串 |
| `POSTGRES_DB` | `random_pictures` | 库名 |
| `POSTGRES_USER` | `postgres` | 用户名 |
| `POSTGRES_PASSWORD` | `postgres` | 密码，**生产环境必须修改** |

### 路径

| 变量 | 默认 | 说明 |
|---|---|---|
| `IMG_ROOT_DIR` | `/app/images` | 图片根目录 |
| `THUMB_CACHE_DIR` | `/app/data/thumbs` | 缩略图缓存目录 |
| `STATIC_ROOT_DIR` | `/app/frontend/static` | 静态资源目录 |
| `FRONTEND_ROOT_DIR` | `/app/frontend` | 前端页面目录 |

### 认证与安全

| 变量 | 默认 | 说明 |
|---|---|---|
| `SECRET_KEY` | 占位字符串 | 会话签名密钥，**生产环境必须修改** |
| `TOKEN_EXPIRE_DAYS` | `0.5` | 会话有效期（天），默认 12 小时 |
| `COOKIE_SECURE` | `false` | HTTPS 部署时设为 `true` |
| `TRUST_PROXY` | `false` | 反向代理后设为 `true`，否则限流会把所有请求算到代理 IP。也可在后台「系统设置 → 信任反向代理」里切换 |

### 限流与防护（运行时配置的默认值）

| 变量 | 默认 | 说明 |
|---|---|---|
| `RATE_LIMIT_ENABLED` | `true` | 是否启用接口限流 |
| `RATE_LIMIT_PER_MINUTE` | `120` | 图片接口每 IP 每分钟上限 |
| `RATE_LIMIT_AUTH_PER_MINUTE` | `10` | 登录/注册每 IP 每分钟上限 |
| `LOGIN_MAX_FAILURES` | `5` | 账号连续失败多少次后锁定 |
| `LOGIN_IP_MAX_FAILURES` | `20` | 同 IP 窗口期内失败多少次后锁定 |
| `LOGIN_WINDOW_SECONDS` | `900` | 失败计数窗口 |
| `LOGIN_LOCK_BASE_SECONDS` | `60` | 首次锁定秒数，之后逐次翻倍 |
| `LOGIN_LOCK_MAX_SECONDS` | `900` | 单次锁定上限 |
| `REGISTER_GUARD_ENABLED` | `true` | 是否启用注册防批量 |
| `REGISTER_MAX_PER_WINDOW` | `5` | 同一 IP 在窗口期内最多注册账号数 |
| `REGISTER_WINDOW_SECONDS` | `3600` | 注册配额窗口 |
| `REGISTER_MIN_INTERVAL_SECONDS` | `30` | 两次注册的最小间隔 |
| `MAX_SESSIONS_PER_USER` | `10` | 单用户保留的会话数上限 |
| `SESSION_CLEANUP_INTERVAL` | `1800` | 过期会话清理间隔（秒） |
| `MAX_UPLOAD_MB` | `5` | 单张图片上传大小上限（MB） |

### 首页分页

| 变量 | 默认 | 说明 |
|---|---|---|
| `CATEGORY_PAGE_SIZE` | `6` | 分类详情页每页图片数 |
| `HOME_PAGE_SIZE` | `6` | 首页每页分类数 |
| `ADMIN_PAGE_SIZE` | `20` | 后台列表每页条数 |

---

## 运行时配置

在管理后台「系统设置」中修改。保存后约 5 秒对所有进程生效（进程内有 5 秒快照缓存）；站点信息类（站名 / 备案 / 图标 / 创建日期）改完立即生效。

### 站点信息

| 键 | 说明 |
|---|---|
| `site_name` | 站点名称（≤50 字符） |
| `site_domain` | 站点域名（URL） |
| `icp_beian` | ICP 备案号（≤50 字符） |
| `beian_link` | 备案跳转链接（URL） |
| `timezone` | 站点时区，如 `Asia/Shanghai` |
| `favicon_url` | 站点图标（URL 或本地相对路径） |
| `site_launch_date` | 项目创建日期 `YYYY-MM-DD`，首页「稳定交付 N 天」按它计算；留空则不显示天数 |

### 功能开关

| 键 | 说明 |
|---|---|
| `show_beian_info` | 页脚展示备案信息 |
| `enable_access_log` | 服务端记录访问日志 |
| `enable_path_traversal_protection` | 校验 `/image?path=` 参数 |
| `enable_hotlink_protection` | 校验 Referer |
| `enable_ip_blacklist` | 启用 IP 黑名单 |
| `trust_proxy` | 信任反向代理传来的 `X-Forwarded-For`（限流、登录记录、审核日志都按真实客户端 IP 记） |

### 上传限制

| 键 | 范围 | 说明 |
|---|---|---|
| `max_upload_mb` | 1–100 | 单张图片上传大小上限（MB）。按**剥离元数据后的落盘体积**判断——因为是无损剥离，落盘体积≈原始体积，所以这个值基本等于「原始文件大小上限」；原始体积超过上限 4 倍时直接拒绝 |

### 限流

| 键 | 范围 | 说明 |
|---|---|---|
| `enable_rate_limit` | true/false | 限流总开关 |
| `rate_limit_per_minute` | 1–10000 | 图片接口每 IP 每分钟上限 |
| `rate_limit_auth_per_minute` | 1–1000 | 登录/注册每 IP 每分钟上限 |

### 登录防护与会话

| 键 | 范围 | 说明 |
|---|---|---|
| `enable_login_guard` | true/false | 登录防爆破总开关 |
| `login_max_failures` | 1–50 | 账号失败阈值 |
| `login_ip_max_failures` | 1–500 | IP 失败阈值 |
| `login_lock_base_seconds` | 5–3600 | 首次锁定秒数 |
| `login_lock_max_seconds` | 30–86400 | 锁定上限秒数 |
| `max_sessions_per_user` | 1–100 | 单用户会话上限 |
| `session_cleanup_interval` | 60–86400 | 清理间隔（秒） |
| `audit_retention_days` | 7–3650 | 审核日志保留天数 |

### 注册防护

| 键 | 范围 | 说明 |
|---|---|---|
| `enable_register_guard` | true/false | 注册防批量总开关 |
| `register_max_per_window` | 1–100 | 每 IP 配额 |
| `register_window_seconds` | 60–86400 | 配额窗口（秒） |
| `register_min_interval_seconds` | 0–3600 | 两次注册最小间隔，0 表示不限 |

超出范围或类型错误时接口返回 400，不会写入数据库。

---

## 修改方式

**管理后台**：系统设置 → 修改 → 保存设置（推荐）

**接口**：

```bash
# 单条
curl -X PUT http://localhost:8081/api/admin/system/config \
  -H "Content-Type: application/json" -b cookie.txt \
  -d '{"key":"rate_limit_per_minute","value":"200"}'

# 批量
curl -X PUT http://localhost:8081/api/admin/system/config/batch \
  -H "Content-Type: application/json" -b cookie.txt \
  -d '{"items":{"rate_limit_per_minute":"200","enable_login_guard":"true"}}'
```

**恢复默认**：管理后台点「恢复默认」，或 `POST /api/admin/system/config/reset`。
恢复的是环境变量给出的默认值，不是硬编码常量。

---

## 多进程说明

限流计数在进程内存中，多 worker 部署时每个进程各算一份，实际总上限约为 `单进程限额 × worker 数`。

登录锁定、注册配额、会话存储在数据库，多进程共享同一份计数，不受此影响。
