# 随机图API - 个性化配置指南 v2.0

本文档介绍如何通过环境变量自定义站点的所有个性化设置，包含最新功能配置。

## 📋 配置文件位置

所有配置通过 `docker-compose.yml` 文件中的 `environment` 部分进行设置。

## ⚙️ 可用配置项
### 基础配置
```yaml
- SITE_NAME=随机图API           # 站点名称，显示在页面标题和logo
- PORT=8081                    # 服务端口（容器内部，固定配置）
- IMG_ROOT_DIR=/app/images     # 图片目录路径（固定配置）
- PUID=1000                    # 容器用户ID（默认1000兼容大多数Linux）
- PGID=1000                    # 容器组ID（默认1000兼容大多数Linux）
```

### 站点个性化配置
```yaml
- FAVICON_URL=                 # 站点图标URL，支持本地或远程，留空则无图标
- ICP_BEIAN_CODE=              # ICP备案号，如"京ICP备12345678号"，留空则不显示
- ICP_BEIAN_URL=               # 备案信息链接，如"https://beian.miit.gov.cn"，留空则无链接
```

### 导航栏按钮配置
```yaml
- NAV_HOME_URL=/               # 首页按钮链接（默认即可）
- NAV_BLOG_URL=                # 博客按钮链接，填写后显示"博客"按钮
- NAV_GITHUB_URL=              # GitHub按钮链接，填写后显示"开源地址"按钮
- NAV_CUSTOM_TEXT=             # 自定义按钮文本，如"联系我们"
- NAV_CUSTOM_URL=              # 自定义按钮链接，与NAV_CUSTOM_TEXT配对使用
```

### 文本内容配置（新增）
```yaml
- WELCOME_MESSAGE=欢迎使用是飞鱼随机图API     # 首页欢迎语（可自定义）
- COPYRIGHT_NOTICE=本站所有图片均为用户上传，仅作学习所有，若有侵权，请与我联系我将及时删除！  # 版权声明（可自定义）
```

### 性能配置（重要提示）
```yaml
# 重要：为了最佳视觉效果（每行显示3个），建议设置为3的倍数
- CATEGORY_PAGE_SIZE=6         # 分类详情页每页显示图片数量（推荐：3/6/9/12等）
- HOME_PAGE_SIZE=6             # 首页每页显示分类数量（推荐：3/6/9/12等）

# 非3的倍数可能导致最后一排留空，影响布局美观
```

## 🎯 配置示例

### 示例1：个人博客站点
```yaml
environment:
  - SITE_NAME=我的图片库
  - FAVICON_URL=https://example.com/favicon.ico
  - NAV_BLOG_URL=https://blog.example.com
  - NAV_GITHUB_URL=https://github.com/username
  - NAV_CUSTOM_TEXT=关于我们
  - NAV_CUSTOM_URL=https://example.com/about
  - WELCOME_MESSAGE=欢迎使用我的专属图片库
  - COPYRIGHT_NOTICE=本图库所有图片均为原创，未经授权禁止转载
  - CATEGORY_PAGE_SIZE=9
  - HOME_PAGE_SIZE=6
```

### 示例2：企业内网部署
```yaml
environment:
  - SITE_NAME=公司图库系统
  - FAVICON_URL=/image?path=logo.png
  - NAV_CUSTOM_TEXT=员工手册
  - NAV_CUSTOM_URL=http://intranet/employee-guide
  - WELCOME_MESSAGE=欢迎使用公司图片资源库
  - COPYRIGHT_NOTICE=本系统仅供内部使用，严禁外传
  - CATEGORY_PAGE_SIZE=12
  - HOME_PAGE_SIZE=3
```

### 示例3：最小化配置
```yaml
environment:
  - SITE_NAME=简洁图库
  # 其他配置留空使用默认值
```

## 🔧 配置生效方式

### 1. 新建部署
```bash
# 首次部署直接生效
docker compose up -d
```

### 2. 修改现有配置
```bash
# 修改docker-compose.yml后重启服务
docker compose down
docker compose up -d
```

### 3. 环境变量优先级
- 环境变量配置 > 代码默认值
- 留空的配置项使用默认值
- 修改后需要重启容器生效

## ?? 布局设计说明

### 网格布局原则
- **首页**：每行固定显示3个分类卡片
- **分类页**：每行固定显示3张图片
- **响应式**：在平板/手机上自动调整为2列或1列

### 分页配置建议
- 大屏幕设备：9或12（每页显示更多内容）
- 中等屏幕：6（平衡内容密度和加载速度）
- 移动设备：3（优化触控体验）

## 🛠️ 特殊功能

### 权限自动修复
- 镜像内置自动权限修复脚本
- 启动时自动处理挂载目录权限问题
- 无需手动chmod/chown操作

### 实时文件同步
- 支持运行中新增/删除图片
- 3秒内自动同步到Web界面
- 无需重启服务

## ❓ 常见问题

### Q: 配置修改后不生效？
A: 确保执行了 `docker compose down && docker compose up -d`

### Q: 分页设置多少合适？
A: 强烈建议使用3的倍数，以获得最佳布局效果

### Q: 如何自定义版权声明？
A: 修改 `COPYRIGHT_NOTICE` 环境变量内容即可

### Q: 权限问题如何解决？
A: 使用最新镜像，内置自动权限修复功能

---

**文档版本**: v2.0 | **更新日期**: 2026年1月4日  
**对应镜像**: [镜像仓库地址]/yunjian101/random-pictures-api:latest