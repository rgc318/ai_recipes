#!/usr/bin/env bash
set -euo pipefail

# ========================
# 配置区（建议放 .env 里）
# ========================
: "${PROD_DB_URI:?必须设置生产库连接 URI}"
: "${TEST_DB_URI:?必须设置测试库连接 URI}"
DUMP_FILE="${DUMP_FILE:-/tmp/prod_dump_$(date +%Y%m%d_%H%M%S).dump}"
CLEAR_TARGET="${CLEAR_TARGET:-true}"
SYNC_TABLES="${SYNC_TABLES:-}" # 多表用逗号分隔，例如 public.users,public.orders

echo "=== 🚀 开始 PostgreSQL 数据同步 ==="
echo "生产库: $PROD_DB_URI"
echo "目标库: $TEST_DB_URI"
echo "导出文件: $DUMP_FILE"

# ========================
# 导出生产库
# ========================
echo "=== 📤 导出生产库数据 ==="
if [[ -n "$SYNC_TABLES" ]]; then
  TABLE_ARGS=()
  IFS=',' read -ra TABLE_LIST <<< "$SYNC_TABLES"
  for t in "${TABLE_LIST[@]}"; do
    TABLE_ARGS+=("-t" "$t")
  done
  pg_dump -Fc "${PROD_DB_URI}" -f "${DUMP_FILE}" "${TABLE_ARGS[@]}"
else
  pg_dump -Fc "${PROD_DB_URI}" -f "${DUMP_FILE}"
fi
echo "✅ 导出完成"

# ========================
# 清空目标库
# ========================
if [[ "$CLEAR_TARGET" == "true" ]]; then
  echo "=== 🧹 清空目标库 schema ==="
  psql "${TEST_DB_URI}" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
  echo "✅ 目标库已清空"
fi

# ========================
# 导入到目标库
# ========================
echo "=== 📥 导入数据到目标库 ==="
pg_restore --no-owner --no-privileges -d "${TEST_DB_URI}" "${DUMP_FILE}"
echo "✅ 导入完成"

# ========================
# 可选：数据脱敏
# ========================
if [[ "${ENABLE_ANONYMIZE:-false}" == "true" ]]; then
  echo "=== 🔒 执行数据脱敏 ==="
  # 示例：把邮箱替换成测试邮箱
  psql "${TEST_DB_URI}" -c "UPDATE users SET email = CONCAT('user', id, '@test.com');"
  # 示例：把手机号中间四位打星
  psql "${TEST_DB_URI}" -c "UPDATE users SET phone = regexp_replace(phone, '(\\d{3})\\d{4}(\\d{4})', '\\1****\\2');"
  echo "✅ 数据脱敏完成"
fi

echo "=== 🎉 数据同步完成 ==="
