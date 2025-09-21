# Dockerfile (适配 uv 版本)

# --- Stage 1: builder ---
# 这个阶段专门用来安装依赖
FROM python:3.12-slim as builder

# 安装 uv
# uv 是一个静态二进制文件，可以直接下载使用，非常适合 Docker
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# 将 uv 添加到系统 PATH
ENV PATH="/root/.cargo/bin:${PATH}"

# 设置工作目录
WORKDIR /app

# (最佳实践) 先只复制依赖定义文件
COPY pyproject.toml ./

# 使用 uv 高效地安装依赖
# --system: 将包安装到全局的 site-packages，这是在 Docker 容器内的推荐做法
# --no-cache: uv 默认就不怎么用缓存，但明确指定可以确保镜像体积最小
RUN uv pip install --system --no-cache --no-deps .

# --- Stage 2: final ---
# 这是最终的生产镜像，它会非常轻量
FROM python:3.12-slim

# 创建一个非 root 用户来运行应用，增强安全性
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 设置工作目录
WORKDIR /app

# (关键) 从 builder 阶段，只复制安装好的依赖库过来
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# 复制你项目的所有代码
# --chown: 确保复制过来的文件属于我们创建的 appuser 用户
COPY --chown=appuser:appgroup . .

# 将工作目录的所有权也交给 appuser
RUN chown -R appuser:appgroup /app

# 切换到非 root 用户
USER appuser

# 暴露端口
EXPOSE 8000

# 定义容器启动时要执行的命令
# 使用 Gunicorn 作为生产级的 ASGI 服务器来运行 Uvicorn worker
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "app.main:app", "-b", "0.0.0.0:8000"]

# Dockerfile (适配 uv 版本)

# --- Stage 1: builder ---
# 这个阶段专门用来安装依赖
FROM python:3.12-slim as builder

# 安装 uv
# uv 是一个静态二进制文件，可以直接下载使用，非常适合 Docker
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# 将 uv 添加到系统 PATH
ENV PATH="/root/.local/bin:/root/.cargo/bin:${PATH}"


# 设置工作目录
WORKDIR /app

# (最佳实践) 先只复制依赖定义文件
COPY pyproject.toml uv.lock* ./




# 使用 uv 高效地安装依赖
# --system: 将包安装到全局的 site-packages，这是在 Docker 容器内的推荐做法
# --no-cache: uv 默认就不怎么用缓存，但明确指定可以确保镜像体积最小
# RUN uv pip install --system --no-cache --no-deps .
# 1. 先编译出一个精确的依赖锁文件
RUN uv pip sync --system --no-cache uv.lock
# --- Stage 2: final ---
# 这是最终的生产镜像，它会非常轻量
FROM python:3.12-slim

# 创建一个非 root 用户来运行应用，增强安全性
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 设置工作目录
WORKDIR /app

# (关键) 从 builder 阶段，只复制安装好的依赖库过来
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# 复制你项目的所有代码
# --chown: 确保复制过来的文件属于我们创建的 appuser 用户
COPY --chown=appuser:appgroup . .

# 将工作目录的所有权也交给 appuser
RUN chown -R appuser:appgroup /app

# 切换到非 root 用户
USER appuser

# 暴露端口
EXPOSE 8000

# 定义容器启动时要执行的命令
# 使用 Gunicorn 作为生产级的 ASGI 服务器来运行 Uvicorn worker
CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "app.main:app", "-b", "0.0.0.0:8000"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8000/auth/health || exit 1
