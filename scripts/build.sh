#!/usr/bin/env sh
# scripts/build.sh —— 清理并构建 sdist 与 wheel，输出产物清单与 sha256
#
# 行为：
#   1. 清理 dist/ 与 build/
#   2. python -m build 生成 sdist（.tar.gz）与 wheel（.whl）
#   3. 打印产物清单（含字节大小）与 sha256 校验和
#
# 用法：
#   sh scripts/build.sh
#   PYTHON=python3.12 sh scripts/build.sh
set -eu

# 定位仓库根目录（本脚本位于 <root>/scripts 下）
SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
cd "$ROOT_DIR"

# 选择 Python：优先使用项目虚拟环境
if [ -x ".venv/bin/python" ]; then
  PY=".venv/bin/python"
elif [ -x ".venv/Scripts/python.exe" ]; then
  PY=".venv/Scripts/python.exe"
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY="${PYTHON:-python}"
fi

echo "清理旧的构建产物：dist/ build/"
rm -rf dist build

echo "构建 sdist 与 wheel（python -m build）"
"$PY" -m build

echo ""
echo "构建产物清单："
found=0
for f in dist/*; do
  if [ -e "$f" ]; then
    found=1
    # 用参数展开去掉 wc 输出的前导空格，避免引入管道
    size=$(wc -c < "$f")
    size=${size##* }
    printf '  %s  (%s 字节)\n' "$f" "$size"
  fi
done
if [ "$found" -eq 0 ]; then
  echo "错误：dist/ 为空，构建似乎未生成任何产物。" >&2
  exit 1
fi

# ---- sha256 校验和（按可用工具自动选择） ----------------------------------
SUM_CMD=""
if command -v sha256sum >/dev/null 2>&1; then
  SUM_CMD="sha256sum"
elif command -v shasum >/dev/null 2>&1; then
  SUM_CMD="shasum -a 256"
elif command -v openssl >/dev/null 2>&1; then
  SUM_CMD="openssl dgst -sha256"
fi

echo ""
if [ -n "$SUM_CMD" ]; then
  echo "sha256 校验和："
  # shellcheck disable=SC2086  # SUM_CMD 可能包含参数（如 shasum -a 256）
  $SUM_CMD dist/*
else
  echo "未找到 sha256sum / shasum / openssl，跳过校验和计算。" >&2
fi
