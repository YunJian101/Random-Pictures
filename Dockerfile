# =============================================================================
# 随机图 API - 运行镜像
#
# 依赖全部是纯 Python 包或有 manylinux wheel（Pillow / asyncpg / uvloop），
# 因此不需要 apt 安装编译头文件，构建更快、镜像更小。
# 如在特殊架构上需要从源码编译 Pillow，再补装 libjpeg/libpng/libwebp 的开发包。
# =============================================================================
# 基础镜像可用构建参数替换，例如走内网镜像仓库：
#   docker compose build --build-arg BASE_IMAGE=registry.local/library/python:3.11-slim
ARG BASE_IMAGE=python:3.11-slim
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Shanghai

WORKDIR /app

# 需要走国内镜像时：docker compose build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_INDEX_URL=https://pypi.org/simple

# 先装依赖再拷代码，改代码时不会让依赖层缓存失效
COPY requirements.txt .
RUN pip install --no-cache-dir -i "$PIP_INDEX_URL" -r requirements.txt

# 复制项目文件（.dockerignore 已排除 .git / 本地缓存等）
COPY . .

# 运行期目录（图片目录通常由 compose 挂载覆盖）
RUN mkdir -p /app/images /app/data

EXPOSE 8081

CMD ["python", "-m", "backend.main"]
