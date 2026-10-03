#!/usr/bin/env sh
# scripts/setup.sh —— 在 Linux / macOS / WSL 上创建本地开发环境
#
# 行为：
#   1. 检测 Python 版本（要求 >= 3.10）
#   2. 创建 .venv 虚拟环境（已存在则复用，脚本幂等）
#   3. 升级 pip / setuptools / wheel
#   4. 以可编辑模式安装项目及 dev 额外依赖（.[dev]）
#   5. 打印激活方式与常用命令
#
# 用法：
#   sh scripts/setup.sh
#   PYTHON=python3.12 sh scripts/setup.sh      # 指定解释器
#   VENV_DIR=.venv312 sh scripts/setup.sh      # 指定虚拟环境目录
set -eu

# 定位仓库根目录（本脚本位于 <root>/scripts 下）
SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
cd "$ROOT_DIR"

VENV_DIR=${VENV_DIR:-.venv}
MIN_MAJOR=3
MIN_MINOR=10

# ---- 1. 选择用于创建 venv 的解释器 ----------------------------------------
PYTHON_BIN=${PYTHON:-}
if [ -z "$PYTHON_BIN" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN=python
  else
    echo "错误：未找到 python3 / python，请先安装 Python ${MIN_MAJOR}.${MIN_MINOR}+。" >&2
    exit 1
  fi
fi

# 版本检测（>= 3.10），比较逻辑交给 Python 自己完成，避免 shell 里做浮点比较
if ! "$PYTHON_BIN" -c "import sys; sys.exit(0 if sys.version_info >= (${MIN_MAJOR}, ${MIN_MINOR}) else 1)"; then
  current=$("$PYTHON_BIN" -c "import sys; print('%d.%d.%d' % sys.version_info[:3])")
  echo "错误：需要 Python ${MIN_MAJOR}.${MIN_MINOR}+，当前为 ${current}（${PYTHON_BIN}）。" >&2
  exit 1
fi
current=$("$PYTHON_BIN" -c "import sys; print('%d.%d.%d' % sys.version_info[:3])")
echo "使用解释器：${PYTHON_BIN} (${current})"

# ---- 2. 创建虚拟环境（幂等） ----------------------------------------------
if [ -x "$VENV_DIR/bin/python" ]; then
  echo "已存在虚拟环境：${VENV_DIR}（跳过创建）"
else
  echo "创建虚拟环境：${VENV_DIR}"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VPY="${VENV_DIR}/bin/python"

# ---- 3 & 4. 升级工具链并安装依赖 ------------------------------------------
echo "升级 pip / setuptools / wheel"
"$VPY" -m pip install --upgrade pip setuptools wheel

echo "安装项目（可编辑模式）及 dev 额外依赖：.[dev]"
"$VPY" -m pip install -e ".[dev]"

# ---- 5. 提示 ---------------------------------------------------------------
echo ""
echo "完成 ✅ 开发环境已就绪。"
echo "激活虚拟环境："
echo "  POSIX sh / bash / zsh:  . ${VENV_DIR}/bin/activate"
echo "  fish:                   source ${VENV_DIR}/bin/activate.fish"
echo ""
echo "常用命令："
echo "  sh scripts/check.sh          # 完整质量门禁（格式/lint/类型/测试）"
echo "  sh scripts/test.sh --fast    # 运行测试并跳过 slow 用例"
echo "  pre-commit install           # 安装提交前钩子"
