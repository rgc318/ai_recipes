#!/usr/bin/env bash
set -euo pipefail

# ========================
# 配置区（从 .env 文件读取）
# ========================
: "${PGPROD_HOST:?必须设置生产库主机}"
: "${PGPROD_PORT:?必须设置生产库端口}"
: "${PGPROD_USER:?必须设置生产库用户名}"
: "${PGPROD_PASSWORD:?必须设置生产库密码}"
: "${PGPROD_DB:?必须设置生产库数据库名}"

: "${PGTEST_HOST:?必须设置测试库主机}"
: "${PGTEST_PORT:?必须设置测试库端口}"
: "${PGTEST_USER:?必须设置测试库用户名}"
: "${PGTEST_PASSWORD:?必须设置测试库密码}"
: "${PGTEST_DB:?必须设置测试库数据库名}"

DUMP_FILE="${DUMP_FILE:-/tmp/prod_dump_$(date +%Y%m%d_%H%M%S).dump}"
CLEAR_TARGET="${CLEAR_TARGET:-true}"
ENABLE_ANONYMIZE="${ENABLE_ANONYMIZE:-false}"

echo "=== 🚀 开始 PostgreSQL 数据同步 ==="
echo "生产库: $PGPROD_HOST:$PGPROD_PORT/$PGPROD_DB"
echo "目标库: $PGTEST_HOST:$PGTEST_PORT/$PGTEST_DB"
echo "导出文件: $DUMP_FILE"

# ========================
# 导出生产库
# ========================
echo "=== 📤 导出生产库数据 ==="
export PGPASSWORD="$PGPROD_PASSWORD"

# 直接导出整个数据库，排除 alembic_version
pg_dump -h "$PGPROD_HOST" -p "$PGPROD_PORT" -U "$PGPROD_USER" -d "$PGPROD_DB" \
    -Fc -f "$DUMP_FILE" \
    --exclude-table=public.alembic_version

echo "✅ 导出完成"

# ========================
# 清空目标库
# ========================
export PGPASSWORD="$PGTEST_PASSWORD"
if [[ "$CLEAR_TARGET" == "true" ]]; then
  echo "=== 🧹 清空目标库 schema ==="
  psql -h "$PGTEST_HOST" -p "$PGTEST_PORT" -U "$PGTEST_USER" -d "$PGTEST_DB" \
       -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
  echo "✅ 目标库已清空"
fi

# ========================
# 导入到目标库
# ========================
echo "=== 📥 导入数据到目标库 ==="
pg_restore -h "$PGTEST_HOST" -p "$PGTEST_PORT" -U "$PGTEST_USER" -d "$PGTEST_DB" \
    --no-owner --no-privileges "$DUMP_FILE"
echo "✅ 导入完成"

# ========================
# 可选：数据脱敏
# ========================
if [[ "$ENABLE_ANONYMIZE" == "true" ]]; then
  echo "=== 🔒 执行数据脱敏 ==="
  # 示例：把邮箱替换成测试邮箱
  psql -h "$PGTEST_HOST" -p "$PGTEST_PORT" -U "$PGTEST_USER" -d "$PGTEST_DB" \
       -c "UPDATE users SET email = CONCAT('user', id, '@test.com');"
  # 示例：把手机号中间四位打星
  psql -h "$PGTEST_HOST" -p "$PGTEST_PORT" -U "$PGTEST_USER" -d "$PGTEST_DB" \
       -c "UPDATE users SET phone = regexp_replace(phone, '(\\d{3})\\d{4}(\\d{4})', '\\1****\\2');"
  echo "✅ 数据脱敏完成"
fi

echo "=== 🎉 数据同步完成 ==="
