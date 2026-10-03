#!/usr/bin/env sh
# scripts/release.sh —— 发布前校验（dry-run，不会真正上传）
#
# 校验项：
#   1. 工作区干净（无未提交 / 未暂存改动）
#   2. 当前 HEAD 恰好在一个 tag 上
#   3. tag 版本号与 src/dwrg_manager/__init__.py 中的 __version__ 一致
#   4. dist/ 中已有构建产物
#   5. twine check dist/* 通过
#
# 用法：
#   sh scripts/build.sh      # 先构建
#   sh scripts/release.sh    # 再校验
set -eu

# 定位仓库根目录（本脚本位于 <root>/scripts 下）
SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
ROOT_DIR=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)
cd "$ROOT_DIR"

INIT_FILE="src/dwrg_manager/__init__.py"

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

# ---- 1. 工作区是否干净 -----------------------------------------------------
if [ -n "$(git status --porcelain)" ]; then
  echo "错误：工作区不干净，请先提交或处理以下改动：" >&2
  git status --short >&2
  exit 1
fi
echo "[1/5] 工作区干净 ✅"

# ---- 2. 当前 HEAD 是否在 tag 上 -------------------------------------------
tag=$(git describe --tags --exact-match HEAD 2>/dev/null || true)
if [ -z "$tag" ]; then
  echo "错误：当前提交未打 tag，请先创建形如 vX.Y.Z 的 tag（git tag v1.0.0）。" >&2
  exit 1
fi
echo "[2/5] 当前提交位于 tag：$tag ✅"

# ---- 3. 版本号一致性 -------------------------------------------------------
# 去掉可能的 'v' 前缀（纯参数展开，不使用管道）
tag_ver=${tag#v}
pkg_ver=$(sed -n 's/^__version__[[:space:]]*=[[:space:]]*"\(.*\)".*/\1/p' "$INIT_FILE")
if [ -z "$pkg_ver" ]; then
  echo "错误：无法从 ${INIT_FILE} 解析出 __version__。" >&2
  exit 1
fi
if [ "$tag_ver" != "$pkg_ver" ]; then
  echo "错误：tag 版本（${tag_ver}）与 __version__（${pkg_ver}）不一致。" >&2
  exit 1
fi
echo "[3/5] 版本一致：${pkg_ver} ✅"

# ---- 4. dist/ 是否有产物 ---------------------------------------------------
if ! ls dist/* >/dev/null 2>&1; then
  echo "错误：dist/ 为空，请先运行 'sh scripts/build.sh' 构建分发包。" >&2
  exit 1
fi
echo "[4/5] 发现构建产物 ✅"

# ---- 5. twine check（dry-run，不上传） ------------------------------------
echo "[5/5] 校验分发包元数据（twine check，dry-run）"
"$PY" -m twine check dist/*
echo "twine check 通过 ✅（未上传任何内容）"
echo ""
echo "如需真正上传（请谨慎操作，先确认目标仓库）："
echo "  ${PY} -m twine upload dist/*"
