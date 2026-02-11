# 后端模块拆分说明

## 拆分后的目录结构

```
backend/
├── __init__.py
├── main.py                 # 主应用入口（精简后）
├── config.py               # 配置管理
├── database.py             # 数据库连接和初始化
├── cache.py                # 缓存管理
├── schemas.py              # Pydantic 数据模型
├── auth.py                 # 认证业务逻辑
├── image_service.py         # 图片服务业务逻辑
├── utils.py                # 工具函数
├── dependencies.py         # FastAPI 依赖注入
│
├── routers/                # 路由模块（新增）
│   ├── __init__.py
│   ├── page.py            # 页面路由
│   ├── image.py           # 图片API路由
│   ├── auth.py            # 认证API路由
│   ├── user.py            # 用户API路由
│   └── admin.py           # 管理员API路由
│
├── middlewares/            # 中间件模块（新增）
│   ├── __init__.py
│   └── logging.py         # 日志中间件
│
├── handlers/               # 异常处理器模块（新增）
│   ├── __init__.py
│   └── error_handlers.py  # 错误处理
│
└── services/               # 业务服务模块（新增）
    ├── __init__.py
    ├── user_service.py     # 用户服务
    └── session_service.py  # 会话服务
```

## 模块职责说明

### 1. 核心模块
- **main.py**: 应用入口，负责创建FastAPI实例、注册中间件和路由
- **config.py**: 集中管理所有配置项
- **database.py**: 数据库连接管理和初始化
- **cache.py**: 缓存管理器
- **schemas.py**: API请求/响应数据模型
- **dependencies.py**: FastAPI依赖注入

### 2. 业务逻辑模块
- **auth.py**: 认证相关业务逻辑（注册、登录、登出、用户管理）
- **image_service.py**: 图片相关业务逻辑（分类、随机图片等）

### 3. 工具模块
- **utils.py**: 通用工具函数（路径验证、IP获取等）

### 4. 路由模块 (routers/)
- **page.py**: 页面路由（首页、登录页、管理后台等）
- **image.py**: 图片API路由（分类列表、随机图片等）
- **auth.py**: 认证API路由（注册、登录、登出）
- **user.py**: 用户API路由（获取当前用户信息）
- **admin.py**: 管理员API路由（用户管理）

### 5. 中间件模块 (middlewares/)
- **logging.py**: 请求日志中间件

### 6. 异常处理模块 (handlers/)
- **error_handlers.py**: HTTP错误处理器（404、500、422）

### 7. 业务服务模块 (services/)
- **user_service.py**: 用户相关服务（密码哈希、用户验证等）
- **session_service.py**: 会话管理服务（session创建、验证等）

## 拆分优势

1. **职责清晰**: 每个模块专注于单一功能
2. **易于维护**: 代码分散到多个文件，便于定位和修改
3. **便于测试**: 小模块更容易编写单元测试
4. **可扩展性**: 新增功能只需添加对应的路由和模块
5. **团队协作**: 不同开发者可以并行开发不同模块

## 使用说明

### 添加新路由
1. 在 `routers/` 目录下创建新文件
2. 定义路由处理函数
3. 在 `main.py` 中注册路由

### 添加新中间件
1. 在 `middlewares/` 目录下创建新文件
2. 实现中间件类
3. 在 `main.py` 中注册中间件

### 添加新业务逻辑
1. 在 `services/` 目录下创建服务文件
2. 在路由模块中调用服务函数
