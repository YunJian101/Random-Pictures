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

# 复制权限修复脚本
COPY --chown=appuser:appgroup fix-permissions.sh /opt/app/fix-permissions.sh
RUN chmod +x /opt/app/fix-permissions.sh

# 暴露端口
EXPOSE 8081

# 启动命令：优先修复权限，然后启动应用
CMD /opt/app/fix-permissions.sh && echo "🚀 权限修复完成，启动随机图API服务..." && python /opt/app/Random-Pictures.py