# 随机图API - FastAPI版 🎨

## 🚀 项目介绍

### 1.1 核心功能

随机图API是一款高性能的随机图片API服务，使用FastAPI框架开发，支持前后端分离架构，核心特性如下：

- **图片上传和管理系统**：支持上传、管理、分类图片，提供完整的图片管理功能
- **直链访问随机图片**：支持全局随机图片和分类随机图片访问
- **图片分类管理功能**：支持创建、编辑、删除分类，图片可按分类组织
- **用户认证和授权系统**：实现了基于JWT的用户认证和基于角色的权限控制
- **管理员后台管理界面**：提供完整的后台管理功能，支持图片、用户、分类管理
- **系统更新和版本管理功能**：支持系统版本检查和更新
- **自动生成API文档**：提供Swagger UI和ReDoc两种风格的API文档
- **CORS跨域支持**：所有API接口默认开启跨域配置，前端可直接调用
- **响应式UI设计**：Web管理界面适配PC、平板、手机等多种设备

### 1.2 技术栈

- **后端**：Python 3.11 + FastAPI
- **部署**：Docker + Docker Compose
- **网络**：ASGI异步服务器 + CORS跨域支持
- **存储**：本地文件系统 + PostgreSQL数据库
- **文档**：自动生成Swagger UI和ReDoc API文档
- **安全**：JWT令牌认证 + 密码哈希存储 + 基于角色的权限控制

## 📥 快速开始

### 2.1 完整部署（推荐）

```bash
# 拉取项目
git clone https://github.com/YunJian101/Random-Pictures
cd Random-Pictures

# 启动服务
docker compose up -d

# 访问服务
http://localhost:8081
```

### 2.2 方法2：使用Docker Run

```bash
# 启动服务
docker run -d \
  --name random-pictures \
  -p 8081:8081 \
  -v $(pwd)/images:/app/images \
  ghcr.io/yunjian101/random-pictures:latest
```

## 📁 目录结构说明

### 3.1 项目结构

```
Random-Pictures/
├── .github/               # GitHub配置目录
│   └── workflows/         # GitHub Actions工作流配置
│       └── release.yml    # 发布流程配置
├── Donate/                # 收款码图片目录（用于GitHub显示）
│   ├── Alipay-Payment.jpg # 支付宝收款码
│   └── WeChat-Pay.png     # 微信收款码
├── backend/               # FastAPI后端代码
│   ├── api/               # API相关代码
│   ├── core/              # 核心配置和数据库
│   ├── handlers/          # 错误处理
│   ├── middlewares/       # 中间件
│   ├── routers/           # 路由定义
│   ├── schemas/           # Pydantic模型
│   ├── services/          # 业务逻辑服务
│   ├── utils/             # 工具函数
│   ├── __init__.py        # 包初始化
│   └── main.py            # FastAPI应用入口
├── frontend/              # 前端代码目录
│   ├── Status_Code/       # 错误页面
│   ├── static/            # 静态资源
│   ├── index.html         # 首页
│   ├── 注册登录界面.html   # 注册登录页面
│   ├── 用户后台.html       # 用户后台页面
│   └── 管理后台.html       # 管理员后台页面
├── docker-compose.yml     # Docker Compose配置文件
├── Dockerfile             # 镜像构建文件
├── requirements.txt       # Python依赖管理
├── .gitignore             # Git忽略文件
├── CHANGELOG.md           # 变更日志
├── LICENSE                # 许可证文件
└── README.md              # 本文档
```

## ⚙️ 配置说明

### 4.1 docker-compose.yml配置

完整的配置如下：

```yaml
services:
  # 随机图API核心服务
  random-pictures:
    # 构建配置
    build:
      context: .
      dockerfile: Dockerfile
    image: ghcr.io/yunjian101/random-pictures:latest
    container_name: random-pictures                 # 容器名称，便于管理
    ports:
      - "8081:8081"                                 # 端口映射：主机端口:容器端口
    volumes:
    #通常情况下挂在/app/images文件夹到本地就行，不用挂载/app
    # - ./images:/app/images
      - ./:/app
    restart: unless-stopped
    # 重启策略：除非手动停止，否则容器退出后自动重启
    environment:
      # ========== 基础配置 ==========
      - DATABASE_URL=postgresql://postgres:postgres@192.168.11.3:5432/random_pictures  
      # 数据库连接URL：格式为 postgresql://用户名:密码@主机:端口/数据库名
```

**配置说明：**

- **构建配置**：使用项目根目录的Dockerfile构建镜像
- **卷挂载**：默认挂载整个项目目录到容器的/app目录，便于开发和调试
- **端口映射**：将容器的8081端口映射到主机的8081端口
- **数据库配置**：需要配置正确的PostgreSQL数据库连接URL
- **重启策略**：容器退出后自动重启，除非手动停止

**注意事项：**

- 首次部署时，系统会自动初始化数据库结构
- 所有环境变量配置已迁移到数据库中，通过管理后台进行配置
- 性能相关配置（如分页大小）已设置为合理的默认值

## 🔌 API接口使用

### 5.1 接口通用规则

- 所有接口支持GET请求和跨域访问
- 响应格式：图片接口返回二进制流，列表接口返回JSON
- 自动URL编码处理中文路径

### 5.2 核心接口

| 接口 | 参数 | 说明 | 示例 |
|------|------|------|------|
| `/` | 无 | Web管理界面 | `http://localhost:8081/` |
| `/login` | 无 | 登录页面 | `http://localhost:8081/login` |
| `/register` | 无 | 注册页面 | `http://localhost:8081/register` |
| `/admin-panel` | 无 | 管理后台 | `http://localhost:8081/admin-panel` |
| `/user-panel` | 无 | 用户后台 | `http://localhost:8081/user-panel` |
| `/random` | 无 | 全局随机图片 | `http://localhost:8081/random` |
| `/random` | `type=分类名` | 分类随机图片 | `http://localhost:8081/random?type=风景` |
| `/image` | `path=图片路径` | 图片直链 | `http://localhost:8081/image?path=风景/1.jpg` |
| `/api/categories` | `page=页码` | 分类列表API | `http://localhost:8081/api/categories?page=1` |
| `/api/category/images` | `name=分类名&page=页码` | 分类图片API | `http://localhost:8081/api/category/images?name=风景&page=1` |
| `/docs` | 无 | API文档（Swagger UI）| `http://localhost:8081/docs` |
| `/redoc` | 无 | API文档（ReDoc） | `http://localhost:8081/redoc` |

## 🖥️ Web管理界面使用

### 6.1 首页功能

- **分类预览**：网格布局展示图片分类
- **快捷操作**：复制链接、随机查看、查看全部分类
- **使用方法提示**：清晰的操作指引

### 6.2 分类详情页

- **图片展示**：分页显示分类内所有图片
- **大图预览**：点击图片在新窗口查看
- **版权声明**：自动使用配置的版权文本

### 6.3 管理员后台

- **用户管理**：创建、编辑、删除用户，设置用户角色
- **分类管理**：创建、编辑、删除图片分类
- **图片管理**：上传、编辑、删除图片
- **系统设置**：查看系统版本，检查更新

## 🔧 运维管理

### 7.1 图片管理

- **格式支持**：jpg、jpeg、png、gif、webp
- **目录结构**：按分类组织图片，存储在本地文件系统

### 7.2 服务管理命令

```bash
# 启动服务
docker compose up -d

# 停止服务
docker compose down

# 查看状态
docker compose ps

# 查看日志
docker compose logs -f

# 重启服务
docker compose restart
```

## 🛠️ 常见问题排查

### 8.1 权限问题

**问题**：`Permission denied: '/app/images'`

**解决方案**：
```bash
# 1. 预创建目录
mkdir -p ./images && chmod 755 ./images

# 2. 重新部署
docker compose down && docker compose up -d
```

### 8.2 图片不显示

**排查步骤**：
1. 确认images目录下有图片文件
2. 检查容器日志：`docker compose logs`
3. 验证API接口：`curl http://localhost:8081/api/categories`

## 🚀 性能优化

### 9.1 已实现的优化

- **图片缓存机制**：实现了内存缓存，减少重复计算和IO操作
- **数据库查询优化**：为关键表创建了索引，提高查询性能
- **请求响应时间监控**：实现了请求处理时间记录，便于性能分析
- **资源使用效率提升**：使用上下文管理器管理数据库连接，避免资源泄漏

### 9.2 待实现的优化

- **Redis缓存集成**：进一步提升缓存性能
- **对象存储支持**：支持云存储服务，提高存储可靠性
- **负载均衡部署**：支持多实例部署，提高系统可用性

## 📋 安全特性

- **JWT令牌认证**：使用JSON Web Token进行用户认证
- **密码哈希存储**：密码使用安全的哈希算法存储
- **基于角色的权限控制**：实现了管理员和普通用户的权限分离
- **API文档访问权限限制**：API文档仅管理员可访问
- **输入验证**：使用Pydantic模型进行请求数据验证


## 💝 赞助作者

如果本项目对您有帮助，欢迎通过以下方式赞助：

**支付宝 / 微信**：转账时备注"随机图API赞助"

<!-- 支付方式图片 -->
<div style="display: flex; gap: 20px;">
  <img src="Donate/Alipay-Payment.jpg" alt="支付宝支付" width="200">
  <img src="Donate/WeChat-Pay.png" alt="微信支付" width="200">
</div>


## 📄 许可证说明

本项目遵循 **GPL-3.0 许可证** 开源发布。

完整的许可证文本可访问 [GNU官方网站](https://www.gnu.org/licenses/gpl-3.0.html) 查看。

---

**技术支持**：如有问题请提交GitHub Issue或联系作者

**版本**：v1.0.0 | **更新日期**：2026年2月15日