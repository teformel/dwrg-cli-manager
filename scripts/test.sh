#!/usr/bin/env sh
# scripts/test.sh —— 运行测试，支持把参数透传给 pytest
#
# 选项：
#   --unit           只运行标记为 unit 的测试（等价于 -m unit）
#   --integration    只运行标记为 integration 的测试（等价于 -m integration）
#   --fast           跳过 slow 用例（等价于 -m "not slow"）
#   -h, --help       显示帮助
#   其余参数原样透传给 pytest（例如 -k foo、-x、--lf、tests/unit/）
#
# 用法：
#   sh scripts/test.sh                       # 运行 tests/ 下全部测试
#   sh scripts/test.sh --unit
#   sh scripts/test.sh --fast -x
#   sh scripts/test.sh tests/integration -k login
set -eu

usage() {
  cat <<'EOF'
用法: sh scripts/test.sh [选项] [pytest 参数...]

选项:
  --unit          只运行 unit 标记的测试
  --integration   只运行 integration 标记的测试
  --fast          跳过 slow 标记的测试
  -h, --help      显示本帮助

说明:
  未指定目标时默认运行 tests/ 目录；其余参数会原样透传给 pytest。
  注意：--unit/--integration/--fast 同时使用时，以最后一个标记选项为准。
EOF
}

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

marker=""
targets=""

while [ $# -gt 0 ]; do
  case "$1" in
    --unit)         marker="unit";        shift ;;
    --integration)  marker="integration"; shift ;;
    --fast)         marker="not slow";    shift ;;
    -h|--help)      usage; exit 0 ;;
    *)              targets="$targets $1"; shift ;;
  esac
done

# 默认目标：tests/
if [ -z "$targets" ]; then
  targets=" tests/"
fi

if [ -n "$marker" ]; then
  echo "运行测试：标记为 '$marker'，目标：$targets"
  # shellcheck disable=SC2086  # 这里依赖分词把多个参数拆开
  exec "$PY" -m pytest -m "$marker" $targets
else
  echo "运行测试：目标：$targets"
  # shellcheck disable=SC2086  # 这里依赖分词把多个参数拆开
  exec "$PY" -m pytest $targets
fi
