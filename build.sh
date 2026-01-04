#!/bin/bash

# 是飞鱼随机图API - Docker构建脚本
set -e

echo "🚀 开始构建是飞鱼随机图API Docker镜像"

# 检查Docker是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker未安装，请先安装Docker"
    exit 1
fi

# 构建镜像
echo "📦 构建Docker镜像..."
docker build -t random-pictures-api:latest .

# 检查构建是否成功
if [ $? -eq 0 ]; then
    echo "✅ Docker镜像构建成功"
    echo ""
    echo "📋 可用命令:"
    echo "docker run -d -p 8081:8081 -v ./images:/app/images --name random-pictures random-pictures-api:latest"
    echo "docker-compose up -d"
    echo ""
    echo "🌐 访问地址: http://localhost:8081"
else
    echo "❌ Docker镜像构建失败"
    exit 1
fi
