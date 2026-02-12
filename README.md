# 是飞鱼随机图API - 前后端分离版 🎨

## 🚀 项目介绍（项目开发者，刚起步...更换数据库中，项目暂不可用）

### 1.1 核心功能

是飞鱼随机图API是一款高性能、支持实时文件更新的随机图片服务，专为轻量化部署和高可用性设计，核心特性如下：

- **实时文件同步**：运行中新增、删除、修改图片或分类文件夹，Web界面3秒内自动感知变化，无需重启服务
- **权限自动修复**：内置强化权限修复脚本，解决Docker挂载目录的读写权限问题
- **高性能随机算法**：随机接口无需加载全量图片列表，仅读取随机选中的单张图片路径
- **灵活分页机制**：首页分类、分类内图片均支持分页展示，推荐使用3的倍数配置
- **智能缓存策略**：Web预览图缓存7天提升访问速度，随机接口禁用缓存保证随机性
- **全量跨域支持**：所有API接口默认开启跨域配置，前端可直接调用
- **响应式UI设计**：Web管理界面适配PC、平板、手机等多种设备
- **私有仓库支持**：支持推送到私有Docker镜像仓库

### 1.2 技术栈

- 后端：Python 3.11 + FastAPI
- 部署：Docker + Docker Compose
- 网络：ASGI异步服务器 + CORS跨域支持
- 存储：本地文件系统 + SQLite数据库
- 文档：自动生成Swagger UI和ReDoc API文档

## 📥 快速开始

### 2.1 方法1：完整部署（推荐）

```bash
# 拉取项目
git clone https://github.com/YunJian101/Random-Pictures
cd Random-Pictures

# 创建图片目录
mkdir -p images

# 启动服务（内置权限自动修复）
docker compose up -d

# 访问服务
http://localhost:8081
```

### 2.2 方法2：使用Docker Run

```bash
# 如果您有预构建的镜像（Docker Hub或私有仓库）
docker pull ghcr.io/yunjian101/random-pictures:latest

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
├── docker-compose.yml     # Docker Compose配置文件
├── Dockerfile             # 镜像构建文件
├── main.py                # 主程序文件
├── requirements.txt       # Python依赖管理
├── images/                # 图片存储目录
│   ├── 测试/
│   ├── 测试完毕请按你自己的类别来创建文件夹和照片/
│   ├── 豆包AI/
│   ├── 赞助作者/
│   └── Donate/
├── backend/               # FastAPI后端代码
├── frontend/              # 前端代码目录
├── data/                  # 数据库目录
├── .gitignore             # Git忽略文件
├── CHANGELOG.md           # 变更日志
├── LICENSE                # 许可证文件
└── README.md              # 本文档
```

## ⚙️ 配置说明

### 4.1 布局设计说明

**重要**：为了达到最佳的视觉效果，首页和分类页采用**每行固定显示3个**的网格布局。因此以下配置项强烈建议设置为**3的倍数**：

- `CATEGORY_PAGE_SIZE`：分类详情页每页显示图片数量（推荐：3、6、9、12等）
- `HOME_PAGE_SIZE`：首页每页显示分类数量（推荐：3、6、9、12等）

配置非3的倍数时，最后一排可能会留有空位，影响布局美观。

### 4.2 docker-compose.yml配置

完整的环境变量配置如下：

```yaml
services:
  random-pictures:
    image: ghcr.io/yunjian101/random-pictures:latest  
# 镜像名称:标签（可替换为Docker Hub或私有仓库地址）
    container_name: random-pictures
    restart: always
    volumes:
      - ./images:/app/images  # 挂载图片目录（内置权限修复）
    ports:
      - "8081:8081"
    environment:
      # 基础配置
      - SITE_NAME=随机图API
      - IMG_ROOT_DIR=/app/images
      - PORT=8081
      
      # 站点个性化配置
      - FAVICON_URL=
      - ICP_BEIAN_CODE=
      - ICP_BEIAN_URL=
      
      # 导航栏按钮配置
      - NAV_HOME_URL=/
      - NAV_BLOG_URL=
      - NAV_GITHUB_URL=
      - NAV_CUSTOM_TEXT=
      - NAV_CUSTOM_URL=
      
      # 文本内容配置
      - WELCOME_MESSAGE=欢迎使用是飞鱼随机图API
      - COPYRIGHT_NOTICE=本站所有图片均为用户上传，仅作学习所有，若有侵权，请与我联系我将及时删除！
      
      # 性能配置（建议使用3的倍数）
      - CATEGORY_PAGE_SIZE=6
      - HOME_PAGE_SIZE=6
```

### 4.3 个性化配置示例

```
# 自定义配置示例
environment:
  - SITE_NAME=我的专属图库
  - FAVICON_URL=https://example.com/favicon.ico
  - NAV_BLOG_URL=https://blog.example.com
  - NAV_GITHUB_URL=https://github.com/my-repo
  - NAV_CUSTOM_TEXT=联系我们
  - NAV_CUSTOM_URL=https://example.com/contact
  - WELCOME_MESSAGE=欢迎使用我的个人图片库
  - COPYRIGHT_NOTICE=本图库所有图片版权归个人所有
```

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
| `/admin` | 无 | 管理后台 | `http://localhost:8081/admin` |
| `/user` | 无 | 用户后台 | `http://localhost:8081/user` |
| `/random` | 无 | 全局随机图片 | `http://localhost:8081/random` |
| `/random` | `type=分类名` | 分类随机图片 | `http://localhost:8081/random?type=风景` |
| `/image` | `path=图片路径` | 图片直链 | `http://localhost:8081/image?path=风景/1.jpg` |
| `/api/categories` | `page=页码` | 分类列表API | `http://localhost:8081/api/categories?page=1` |
| `/api/category/images` | `name=分类名&page=页码` | 分类图片API | `http://localhost:8081/api/category/images?name=风景&page=1` |
| `/docs` | 无 | API文档（Swagger UI）| `http://localhost:8081/docs` |
| `/redoc` | 无 | API文档（ReDoc） | `http://localhost:8081/redoc` |

## 🖥️ Web管理界面使用

### 6.1 首页功能

- **分类预览**：网格布局展示图片分类，每行3个
- **快捷操作**：复制链接、随机查看、查看全部分类
- **使用方法提示**：清晰的操作指引
- **分页导航**：支持多页分类浏览

### 6.2 分类详情页

- **图片展示**：分页显示分类内所有图片
- **大图预览**：点击图片在新窗口查看
- **版权声明**：自动使用配置的版权文本

### 6.3 响应式设计

- **PC端**：3列网格布局
- **平板端**：2列自适应
- **手机端**：1列优化显示

## 🔧 运维管理

### 7.1 图片管理

- **实时同步**：新增/删除图片3秒内生效
- **自动权限**：镜像启动时自动修复挂载目录权限
- **格式支持**：jpg、jpeg、png、gif、webp

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

### 8.3 布局异常

**确保配置为3的倍数**：
- `CATEGORY_PAGE_SIZE`: 3, 6, 9, 12...
- `HOME_PAGE_SIZE`: 3, 6, 9, 12...

## 🚀 扩展建议

### 9.1 功能扩展
- Web上传界面
- API认证机制
- 图片压缩优化
- CDN集成支持

### 9.2 性能优化
- Redis缓存集成
- 对象存储支持
- 负载均衡部署

## 💝 赞助作者

如果本项目对您有帮助，欢迎通过以下方式赞助：

**支付宝 / 微信**：转账时备注"随机图API赞助"

<!-- 支付方式图片 -->
<div style="display: flex; gap: 20px;">
  <img src="images/Donate/Alipay-Payment.jpg" alt="支付宝支付" width="200">
  <img src="images/Donate/WeChat-Pay.png" alt="微信支付" width="200">
</div>

## 📄 许可证说明

本项目遵循 **GPL-3.0 许可证** 开源发布。

完整的许可证文本可访问 [GNU官方网站](https://www.gnu.org/licenses/gpl-3.0.html) 查看。

---

**技术支持**：如有问题请提交GitHub Issue或联系作者

**版本**：v3.0.0 | **更新日期**：2026年2月11日
