#!/bin/sh
# 这个脚本是执行主应用程序的包装器。
# 它可以确保环境变量被正确地使用。

# set -e: 如果任何命令以非零状态退出，则立即退出脚本。
set -e

# 'exec' 命令会用 gunicorn 进程替换当前的 shell 进程。
# 这对于正确的信号处理（例如，实现优雅关闭）至关重要。
# Gunicorn 将成为容器中的主进程 (PID 1)，
# 这使得它可以从 Docker 守护进程接收到像 SIGTERM 这样的信号。
exec gunicorn -w "${GUNICORN_WORKERS}" -k uvicorn.workers.UvicornWorker app.main:app -b 0.0.0.0:8000
