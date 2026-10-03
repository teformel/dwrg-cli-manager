#!/usr/bin/env sh
# scripts/check.sh —— 本地质量门禁
#
# 依次执行：格式检查 → 静态检查 → 类型检查 → 测试。
# 任一步失败立即以非 0 退出，并打印彩色分节标题。
#
# 用法：
#   sh scripts/check.sh
#   PYTHON=python3.12 sh scripts/check.sh
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

# 颜色：仅在输出为终端时启用，重定向到文件时自动关闭
if [ -t 1 ]; then
  BLUE=$(printf '\033[1;34m')
  GREEN=$(printf '\033[1;32m')
  RED=$(printf '\033[1;31m')
  RESET=$(printf '\033[0m')
else
  BLUE=''
  GREEN=''
  RED=''
  RESET=''
fi

section() {
  printf '\n%s====> %s%s\n' "$BLUE" "$1" "$RESET"
}

fail() {
  printf '%s[失败] %s%s\n' "$RED" "$1" "$RESET" >&2
  exit 1
}

# 执行一个步骤；在 if 语境下运行，避免 set -e 提前中断，从而能打印失败信息
run_step() {
  step_name=$1
  shift
  section "$step_name"
  if "$@"; then
    printf '%s[通过] %s%s\n' "$GREEN" "$step_name" "$RESET"
  else
    fail "$step_name"
  fi
}

run_step "1/4 格式检查 (ruff format --check src)" "$PY" -m ruff format --check src
run_step "2/4 静态检查 (ruff check src)" "$PY" -m ruff check src
run_step "3/4 类型检查 (mypy src)" "$PY" -m mypy src
run_step "4/4 测试 (pytest)" "$PY" -m pytest

printf '\n%s全部检查通过 ✅%s\n' "$GREEN" "$RESET"
