# 随机图 API

一个自托管的随机图片 API。把图片按分类放进图库，用一条链接即可随机取图，附带管理后台、用户中心与开发者文档。

---

## 功能

**图片接口**
- 全局随机 / 按分类随机，直接返回图片流，无需解析 JSON
- 支持 `format` 按格式筛选、`exclude` 排除指定图片
- `w` 参数按需生成缩略图（160/320/480/640/960），磁盘缓存
- 客户端支持时自动输出 WebP（比 JPEG 更小），否则回退 JPEG
- 直链支持 7 天浏览器缓存；随机接口不缓存，每次返回不同图片

**管理后台**
- 图片管理：上传、改分类/文件名、批量移动与删除、导出 ZIP
- 分类管理：增删改、启用/停用
- 用户管理：新建、改资料、重置密码、调整角色、封禁、删除
- 反馈管理：对话式回复、状态流转、删除
- 审核日志：记录管理员操作与异常请求，可按动作/关键字/日期筛选
- 系统设置：站点信息、功能开关、限流与安全参数（保存后即时生效，无需重启）
- 版本更新：检查、执行、备份与回滚

**用户中心**
- 快捷调用：生成带参数的接口地址
- 我的反馈：与管理员的对话线程，可自行关闭
- 账号信息：改用户名/邮箱、改密码
- 登录设备：查看当前账号的会话列表，可逐个下线或退出其它设备

**安全与运维**
- 登录防爆破：账号与 IP 双维度计数，失败达阈值后指数退避锁定
- 注册防批量：按 IP 配额 + 最小间隔
- 接口限流：按 IP 滑动窗口，登录注册单独一档
- 上传图片自动剥离 EXIF/GPS/XMP 等元数据
- 会话治理：过期清理、单用户会话上限、登录设备可追溯
- 审核日志保留期可配置，到期自动清理

---

## 快速开始

需要 Docker 与 Docker Compose。

```bash
git clone https://github.com/YunJian101/Random-Pictures.git
cd Random-Pictures
cp .env.example .env        # 可选，不建也能用默认值启动
docker compose up -d --build
```

启动后访问 `http://localhost:8081`。

首次访问需要登录的页面会跳到注册页，**第一个注册的账号自动成为管理员**。

常用命令：

```bash
docker compose logs -f app     # 查看日志
docker compose down            # 停止（加 -v 会连数据库一起删除）
```

---

## 文档

| 文档 | 内容 |
|---|---|
| [docs/API.md](docs/API.md) | 全部接口、参数、状态码 |
| [docs/CONFIG.md](docs/CONFIG.md) | 环境变量与后台可改的运行时配置 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更记录 |

管理员登录后还可访问 `/docs`（Swagger）与 `/redoc`，这两个页面仅管理员可见。

---

## 项目结构

```
backend/
  api/           依赖注入（当前用户、管理员校验）
  core/          配置、数据库、运行时配置、后台任务
    security/    密码、会话、登录锁定、注册配额
  routers/       路由（按业务域拆分）
  services/      图片、缩略图、用户、审核日志、版本更新
  middlewares/   限流、访问日志、异常请求审计、响应压缩
  handlers/      统一错误处理
  schemas/       Pydantic 模型
frontend/
  *.html         首页 / 登录 / 用户中心 / 管理后台
  static/        样式、脚本、页面级 JS 模块
  Status_Code/   错误页模板
scripts/         冒烟测试与前端模块自检
```

---

## 测试

```bash
# 接口冒烟（标准库，无需额外依赖）
python scripts/smoke_test.py

# 前端 ES 模块依赖自检（需要 Node）
node scripts/check-frontend-modules.mjs
```

冒烟测试默认请求 `http://127.0.0.1:8081`，可用环境变量覆盖：

```bash
BASE_URL=http://192.0.2.10:8081 ADMIN_USER=admin ADMIN_PASSWORD=你的密码 python scripts/smoke_test.py
```

---

## 部署提示

- 生产环境请通过 `.env` 设置 `SECRET_KEY` 与 `POSTGRES_PASSWORD`，不要使用默认值
- 走 HTTPS 时设置 `COOKIE_SECURE=true`
- 使用 Nginx 等反向代理时设置 `TRUST_PROXY=true`，否则限流会把所有请求算到代理 IP 上
- 图片、缩略图、数据库分别放在命名卷中，`docker compose down` 不会丢数据；`down -v` 会

---

## 许可证

GPL-3.0，详见 [LICENSE](LICENSE)。
