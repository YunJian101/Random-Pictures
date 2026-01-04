#!/bin/bash

# 随机图API - 一键安装脚本
set -e

echo "🚀 随机图API一键安装脚本"
echo "=========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检查Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker未安装，请先安装Docker${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}❌ Docker Compose未安装，请先安装Docker Compose${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Docker环境检查通过${NC}"

# 创建必要的目录结构
echo "📁 准备项目目录..."
mkdir -p images

# 检查图片目录权限
echo "🔧 检查并修复权限..."
if [ -d "images" ]; then
    # 尝试修复权限，忽略错误（有些系统可能无相关权限）
    chmod 755 images/ 2>/dev/null || true
    echo -e "${GREEN}✅ 目录权限检查完成${NC}"
fi

# 构建镜像
echo "📦 构建Docker镜像..."
docker build -t random-pictures-api:latest .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 镜像构建成功${NC}"
else
    echo -e "${RED}❌ 镜像构建失败${NC}"
    exit 1
fi

# 启动服务
echo "🚀 启动服务..."
docker-compose up -d

# 等待服务启动
echo "⏳ 等待服务启动（最长30秒）..."
for i in {1..30}; do
    if curl -s http://localhost:8081/ > /dev/null; then
        echo -e "${GREEN}✅ 服务启动成功${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

# 最终验证
if curl -s http://localhost:8081/api/categories 2>/dev/null | grep -q "categories"; then
    echo -e "${GREEN}🎉 随机图API安装完成！${NC}"
else
    echo -e "${YELLOW}⚠️  服务启动中，可能需要更多时间...${NC}"
fi

# 显示访问信息
echo ""
echo "=========================================="
echo -e "${GREEN}🌐 访问地址: http://localhost:8081${NC}"
echo -e "${GREEN}📁 图片目录: ./images/${NC}"
echo ""
echo "📋 使用说明："
echo "   1. 将图片放入 ./images/ 目录"
echo "   2. 支持格式: jpg, jpeg, png, gif, webp"
echo "   3. 每创建一个文件夹就是一个分类"
echo ""
echo "🛠️  管理命令："
echo "   - 重启服务: docker-compose restart"
echo "   - 停止服务: docker-compose down"
echo "   - 查看日志: docker logs Random-Pictures"
echo ""
echo -e "${YELLOW}💡 提示：添加图片后无需重启，网页会自动刷新${NC}"
echo "=========================================="
