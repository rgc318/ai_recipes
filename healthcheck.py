import sys
import http.client
import os

# 从环境变量或默认值获取端口
PORT = int(os.getenv("PORT", 8000))
HOST = "localhost"
PATH = os.getenv("HEALTHCHECK_PATH", "/api/v1/auth/health")

try:
    # 使用 Python 内置的 http.client，无需任何第三方依赖
    conn = http.client.HTTPConnection(HOST, PORT, timeout=5)
    conn.request("GET", PATH)
    response = conn.getresponse()

    # 检查返回的状态码是否为 2xx (成功)
    if 200 <= response.status < 300:
        print(f"Health check passed with status: {response.status}")
        sys.exit(0) # 退出码 0 表示成功
    else:
        print(f"Health check failed with status: {response.status}")
        sys.exit(1) # 退出码 1 表示失败

except Exception as e:
    print(f"Health check failed with error: {e}")
    sys.exit(1)
finally:
    if 'conn' in locals():
        conn.close()
