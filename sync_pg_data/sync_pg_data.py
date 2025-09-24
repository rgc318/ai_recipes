#!/usr/bin/env python3
import os
import subprocess
import logging
from datetime import datetime
from typing import List, Optional

# ========================
# 配置（建议用环境变量注入）
# ========================
PROD_URI = os.getenv("PROD_DB_URI", "postgresql://user:pass@prod-host:5432/prod_db")
TEST_URI = os.getenv("TEST_DB_URI", "postgresql://user:pass@test-host:5432/test_db")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "/tmp")
TABLES = os.getenv("SYNC_TABLES", "").split(",")  # 支持指定部分表同步
CLEAR_TARGET = os.getenv("CLEAR_TARGET", "true").lower() == "true"

# 自动生成导出文件
dump_file = os.path.join(OUTPUT_DIR, f"prod_dump_{datetime.now():%Y%m%d_%H%M%S}.dump")

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

def run_cmd(cmd: List[str]):
    logging.info("运行命令: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)

def export_data():
    logging.info("开始导出生产数据库数据...")
    cmd = ["pg_dump", "-Fc", PROD_URI, "-f", dump_file]
    if TABLES and TABLES != ['']:
        for t in TABLES:
            cmd += ["-t", t]
    run_cmd(cmd)
    logging.info("导出完成: %s", dump_file)

def clear_target_db():
    if CLEAR_TARGET:
        logging.info("清空目标数据库 schema...")
        run_cmd(["psql", TEST_URI, "-c", "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"])
        logging.info("目标数据库已清空")

def import_data():
    logging.info("开始导入数据到测试库...")
    cmd = ["pg_restore", "--no-owner", "--no-privileges", "-d", TEST_URI, dump_file]
    run_cmd(cmd)
    logging.info("导入完成！")

def anonymize_data():
    logging.info("执行数据脱敏...")
    run_cmd(["psql", TEST_URI, "-c", "UPDATE users SET email = CONCAT('user', id, '@test.com');"])

def main():
    export_data()
    clear_target_db()
    import_data()
    # anonymize_data()
    logging.info("✅ 数据同步流程执行完成")

if __name__ == "__main__":
    main()
