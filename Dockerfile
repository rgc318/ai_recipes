# --- Stage 1: builder ---
# 使用更具体的 bookworm 标签来确保基础环境的一致性
FROM python:3.12-slim-bookworm AS builder

# 1. 在一个 RUN 指令中完成工具安装和清理，减小镜像层数
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# 2. 将 uv 安装到系统路径，避免修改 PATH 环境变量，更加简洁
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    ln -s /root/.local/bin/uv /usr/local/bin/uv

# 3. (核心优化) 创建一个独立的虚拟环境来管理依赖
# 这样做可以完美地将项目依赖与系统 Python 环境隔离，是企业级的最佳实践
ENV VENV_PATH=/opt/venv
RUN python3 -m venv $VENV_PATH

# 4. 设置工作目录，并仅复制依赖定义文件以利用缓存
WORKDIR /app
COPY pyproject.toml ./

# 5. 在容器内编译生成锁文件，确保构建环境的独立性
RUN uv pip compile pyproject.toml -o requirements.txt

# 6. 将依赖安装到独立的虚拟环境中
RUN uv pip sync --no-cache --python $VENV_PATH/bin/python requirements.txt


# --- Stage 2: final ---
# 同样使用 bookworm 标签确保基础镜像一致
FROM python:3.12-slim-bookworm

# 1. (新增) 添加 OCI 标准的 LABEL，用于镜像溯源和管理
LABEL maintainer="Your Name <your.email@example.com>" \
      org.opencontainers.image.title="Enterprise Python Service" \
      org.opencontainers.image.description="A production-ready Python web application." \
      org.opencontainers.image.version="1.0.0"

# 2. 设置环境变量
# - PYTHONUNBUFFERED: 确保日志直接输出，不经过缓冲
# - PYTHONDONTWRITEBYTECODE: 避免在容器中生成 .pyc 文件
# - PATH: (核心优化) 将虚拟环境的 bin 目录加入 PATH，这样可以直接执行 gunicorn 等命令
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VENV_PATH=/opt/venv
ENV PATH="$VENV_PATH/bin:$PATH"

# 3. 创建一个低权限的用户和组来运行应用，增强安全性
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser

# 4. 准备应用目录
WORKDIR /app

# 5. (核心优化) 从 builder 阶段复制完整的虚拟环境
# 这比复制 site-packages 和 bin 目录更干净、更可靠
COPY --from=builder $VENV_PATH $VENV_PATH

# 6. 复制应用代码，并设置正确的所有权
# 假设 healthcheck.py 和你的应用代码在同一目录下
COPY --chown=appuser:appgroup . .

RUN mkdir /app/logs && chown -R appuser:appgroup /app

# 8. (新增修改) 作为 appuser，为自己拥有的 entrypoint.sh 脚本添加执行权限
RUN chmod u+x /app/entrypoint.sh

# 7. 切换到非 root 用户
USER appuser



# 8. 暴露应用端口
EXPOSE 8000

# 9. (核心优化) 使用轻量级的 Python 脚本进行健康检查
# 这避免了在最终镜像中安装 curl，保持了镜像的轻量和安全
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD ["python", "healthcheck.py"]

# 10. (优化) 定义容器启动命令
# - 使用环境变量来控制 Gunicorn worker 数量，增强灵活性
# - CMD 使用 exec 格式 (你原来就是对的)，确保应用能正确处理信号，实现优雅停机
ENV GUNICORN_WORKERS=${GUNICORN_WORKERS:-4}
ENTRYPOINT ["/app/entrypoint.sh"]
