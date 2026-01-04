FROM python:3.11-alpine

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    IMG_ROOT_DIR=/app/images \
    PORT=8081 \
    PUID=1000 \
    PGID=1000

# 创建与宿主机匹配的用户组和用户（默认使用1000:1000，兼容大多数Linux）
RUN addgroup -g ${PGID:-1000} appgroup && \
    adduser -u ${PUID:-1000} -G appgroup -D appuser && \
    mkdir -p /opt/app /app/images && \
    chown -R appuser:appgroup /app /opt/app && \
    chmod 755 /app /opt/app /app/images

# 创建基础目录结构（预置正确权限）
RUN mkdir -p /app/images && chmod 755 /app/images

# 切换用户
USER appuser
WORKDIR /opt/app

# 复制应用程序
COPY --chown=appuser:appgroup Random-Pictures.py .
RUN chmod 755 /opt/app/Random-Pictures.py

# 添加强化权限修复脚本
COPY --chown=appuser:appgroup <<'EOF' /opt/app/fix-permissions.sh
#!/bin/sh
# 强化的权限修复脚本 - 确保挂载目录完全可访问
echo "=== 自动权限修复脚本启动 ==="

# 强化的目录创建和权限修复逻辑
if [ ! -d "/app/images" ]; then
    echo "🔧 检测到 /app/images 目录不存在，开始创建和权限修复流程..."
    
    # 1. 创建目录（多层级确保成功）
    mkdir -p /app/images
    
    # 2. 尝试设置容器内用户为所有者（最高优先级）
    echo "➡️ 尝试设置容器用户所有者..."
    chown -R appuser:appgroup /app/images 2>/dev/null && \
        echo "✅ 容器用户所有者设置成功" || \
        echo "⚠️ 容器用户所有者设置受限，尝试宽松权限"
    
    # 3. 确保目录至少可读可执行
    chmod 755 /app/images 2>/dev/null || \
    chmod 777 /app/images 2>/dev/null || true
    
    # 4. 递归设置所有子目录权限
    find /app/images -type d -exec chmod 755 {} \; 2>/dev/null || true
    find /app/images -type f -exec chmod 644 {} \; 2>/dev/null || true
    
    echo "✅ 目录创建和权限修复完成"
else
    echo "📁 /app/images 目录已存在，进行权限修复..."
    
    # 针对现有目录的修复
    chmod 755 /app/images 2>/dev/null || true
    find /app/images -type d -exec chmod 755 {} \; 2>/dev/null || true
    find /app/images -type f -exec chmod 644 {} \; 2>/dev/null || true
    chown -R appuser:appgroup /app/images 2>/dev/null || echo "⚠️ 所有者修复受限，但权限已确保"
fi

# 修复现有的图片目录权限
echo "🔧 修复图片目录权限..."
if [ -d "/app/images" ]; then
    # 1. 修复所有者（如果可能）
    chown -R appuser:appgroup /app/images 2>/dev/null || echo "ℹ️  所有者修复可能受限，继续其他修复..."
    
    # 2. 设置安全的目录权限（755）
    chmod 755 /app/images 2>/dev/null || true
    find /app/images -type d -exec chmod 755 {} \; 2>/dev/null || true
    
    # 3. 设置安全的文件权限（644）
    find /app/images -type f -exec chmod 644 {} \; 2>/dev/null || true
    
    # 4. 验证修复结果
    echo "✅ 权限修复完成，验证可访问性..."
    if [ -r "/app/images" ] && [ -x "/app/images" ]; then
        echo "✅ /app/images 目录可读可执行"
        echo "📁 目录内容预览："
        ls -la /app/images/ 2>/dev/null | head -3 || echo "无法列出目录内容"
    else
        echo "❌ /app/images 目录权限仍有问题，但会继续启动..."
    fi
fi

echo "=== 权限修复脚本完成 ==="
EOF

RUN chmod +x /opt/app/fix-permissions.sh

# 暴露端口
EXPOSE 8081

# 启动命令：优先修复权限，然后启动应用
CMD /opt/app/fix-permissions.sh && echo "🚀 权限修复完成，启动随机图API服务..." && python /opt/app/Random-Pictures.py