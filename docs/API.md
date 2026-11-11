# API 文档

所有接口返回 JSON（图片接口除外），统一格式：

```json
{ "code": 200, "msg": "success", "data": {} }
```

失败时 `code` 与 HTTP 状态码一致，并可能带 `data.error_id` 便于排查。

**认证方式**：登录后服务端写入 HttpOnly Cookie（默认名 `token`），后续请求自动携带，无需额外 Header。

---

## 公开接口

无需登录。

### 随机图片

```
GET /random
```

直接返回图片流，不做缓存。

| 参数 | 类型 | 说明 |
|---|---|---|
| `type` | string | 分类名称，需 URL 编码；留空则从全部分类随机 |
| `format` | string | 限定格式，可逗号组合：`jpg,jpeg,png,gif,webp` |
| `exclude` | string | 排除的图片 ID，逗号分隔，最多 100 个（超出返回 422） |
| `w` | int | 返回该宽度的缩略图，吸附到 160/320/480/640/960 |

```bash
curl -o random.jpg "http://localhost:8081/random?type=%E9%A3%8E%E6%99%AF&w=640"
```

### 图片直链

```
GET /image?path=<相对路径>[&w=宽度]
```

返回固定图片，响应头带 `Cache-Control: public, max-age=604800`（7 天）。

### 缩略图

```
GET /thumb?path=<相对路径>&w=320
```

`w` 默认 320。响应头包含 `X-Thumb-Width`、`X-Thumb-Format` 与 `Vary: Accept`。
客户端声明支持 WebP 时返回 WebP（体积更小），否则返回 JPEG。

### 分类

```
GET /api/categories
```

返回启用中的分类：名称、描述、图片数量。不包含内部 ID 与状态字段。

```
GET /api/category/images?name=<分类名>&page=1
```

返回该分类下的图片列表（含 `name` / `path` / `url`）与分页信息。

### 站点信息

```
GET /api/system/info       # 站点名称、图标，以及开启时才返回的备案信息
GET /api/system/timezone   # 站点时区
GET /api/system/version    # 当前版本号与日期
```

---

## 认证

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/register` | 注册，第一个账号自动成为管理员 |
| POST | `/api/login` | 登录，支持用户名或邮箱 |
| POST | `/api/logout` | 登出，清除当前会话 |
| GET | `/api/auth/verify` | 校验当前会话，返回用户信息 |

登录失败达到阈值时返回 **429**，带 `Retry-After`（秒）与提示文案。

```bash
curl -i -X POST http://localhost:8081/api/login \
  -H "Content-Type: application/json" \
  -d '{"account":"admin","password":"你的密码","remember":true}'
```

---

## 登录用户接口

需要登录，只能操作自己的数据。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/me` | 当前账号信息 |
| PUT | `/api/me` | 修改用户名 / 邮箱 |
| PUT | `/api/me/password` | 修改密码（需原密码，改完其它设备下线） |
| GET | `/api/me/sessions` | 登录设备列表 |
| DELETE | `/api/me/sessions/{sid}` | 下线指定设备 |
| POST | `/api/me/sessions/revoke-others` | 退出除当前外的全部设备 |
| POST | `/api/feedbacks` | 提交反馈 |
| GET | `/api/my/feedbacks` | 我的反馈列表 |
| POST | `/api/my/feedbacks/{id}/messages` | 在反馈线程中回复 |
| PUT | `/api/my/feedbacks/{id}/status` | 自行关闭反馈 |

`sid` 是会话的短标识（由 token 派生），不是 token 本身。

---

## 管理接口

全部需要管理员身份，非管理员返回 403。

### 统计与日志

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/admin/stats` | 图片/分类/用户/反馈汇总 + 近 24 小时安全事件 |
| GET | `/api/admin/audit-logs` | 审核日志，支持 `page` `page_size` `action` `keyword` `start` `end` |

### 图片

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/images` | 图片列表，支持 `page` `category` `keyword` `sort` |
| GET | `/api/image/{id}` | 图片详情 |
| PUT | `/api/image/{id}` | 修改文件名 / 分类 |
| DELETE | `/api/image/{id}` | 删除图片 |
| POST | `/api/admin/upload` | 上传图片（multipart，`files` + `category`） |
| POST | `/api/admin/batch-action` | 批量操作：`download` / `move` / `delete` |

`sort` 可选：`created_desc`、`created_asc`、`size_desc`、`size_asc`、`views_desc`、`name_asc`。

### 分类

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/admin/categories` | 全量分类（含停用的） |
| POST | `/api/admin/categories` | 新建 |
| PUT | `/api/admin/categories/{id}` | 修改名称/描述/状态 |
| DELETE | `/api/admin/categories/{id}` | 删除，其下图片转为未分类 |

### 用户

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/users` | 用户列表 |
| GET | `/api/users/{id}` | 用户详情 |
| POST | `/api/users` | 新建用户 |
| PUT | `/api/users/{id}` | 修改资料、重置密码、调整角色 |
| DELETE | `/api/users/{id}` | 删除用户及其反馈 |
| PUT | `/api/users/{id}/ban` | 封禁（可带 `reason`） |
| PUT | `/api/users/{id}/unban` | 解封 |

### 反馈

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/admin/feedbacks` | 反馈列表 |
| GET | `/api/admin/feedbacks/{id}` | 反馈详情（含消息线程） |
| POST | `/api/admin/feedbacks/{id}/messages` | 回复并置为「处理中」 |
| PUT | `/api/admin/feedbacks/{id}/status` | 变更状态 |
| DELETE | `/api/admin/feedbacks/{id}` | 删除 |

状态取值：`pending`（待处理）、`processing`（处理中）、`resolved`（已解决）、`closed`（已关闭）。
`pending` 状态下用户不可回复；`resolved` / `closed` 后双方均不可回复。

### 系统配置与更新

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/admin/system/config` | 读取全部配置 |
| PUT | `/api/admin/system/config` | 修改单条（`key` + `value`） |
| PUT | `/api/admin/system/config/batch` | 批量修改（`items` 对象） |
| POST | `/api/admin/system/config/reset` | 全部恢复默认值 |
| GET | `/api/system/backups` | 备份列表 |
| GET | `/api/system/check-update` | 检查新版本；返回 `manual_update_required` / `manual_update_hint`，为 `true` 表示跨大版本（如 1.x → 2.x），只能手动更新 |
| POST | `/api/system/execute-update` | 执行更新；跨大版本时返回 `manual_update_required: true` 且不改动任何文件。正常更新完成后服务会自动重启 |
| POST | `/api/system/rollback` | 回滚到指定备份（可传文件名或备份目录内的路径）；成功后服务会自动重启 |

> 更新与回滚只替换磁盘上的代码，完成后服务会自己重启（多 worker 由 uvicorn 重启该 worker，单进程由容器 restart 策略拉起），期间约 10~30 秒无法访问。

配置项名称与取值范围见 [CONFIG.md](CONFIG.md)。

---

## 状态码

| 状态码 | 含义 |
|---|---|
| 200 | 成功 |
| 400 | 参数格式错误 |
| 401 | 未登录或会话失效 |
| 403 | 已登录但权限不足 / 账号被封禁 |
| 404 | 资源不存在 |
| 409 | 当前状态不允许该操作（如对已关闭的反馈回复） |
| 422 | 参数校验失败（含路径穿越、`format` 非法、`exclude` 超限） |
| 429 | 触发限流或登录锁定，响应带 `Retry-After` |
| 500 | 服务端异常，响应中带 `error_id` |

浏览器直接访问且被限流时返回 HTML 错误页，程序调用返回 JSON。
