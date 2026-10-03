#!/usr/bin/env sh
# scripts/install-remote.sh —— 面向「远程主机 / 容器内」的一次性部署
#
# 行为：
#   1. 把仓库同步到目标目录（优先 rsync，找不到则退回 cp -R）
#   2. 在目标目录创建 .venv 虚拟环境并安装项目
#   3. 生成 systemd user unit 模板（deploy/dwrg.service）
#   4. 打印后续启用步骤
#
# 说明：dwrg 是面向用户的「交互式 CLI」，本身不应该作为常驻服务运行。
#       因此生成的 unit 只给出 Type=oneshot 的一次性任务示例（例如定时做
#       资源校验 / 更新），并在其中用注释标明用途，请按需修改。
#
# 用法：
#   sh scripts/install-remote.sh                       # 源=仓库根，目标=$HOME/.local/share/dwrg-cli
#   sh scripts/install-remote.sh /path/to/repo /opt/dwrg
#   DEST_DIR=/srv/dwrg sh scripts/install-remote.sh
set -eu

SCRIPT_DIR=$(CDPATH= cd "$(dirname "$0")" && pwd)
DEFAULT_SRC=$(CDPATH= cd "$SCRIPT_DIR/.." && pwd)

SRC_DIR=${1:-${SRC_DIR:-$DEFAULT_SRC}}
# set -u 下 $HOME 可能未定义，因此给出回退值
DEST_DIR=${2:-${DEST_DIR:-${HOME:-/root}/.local/share/dwrg-cli}}

echo "源目录：${SRC_DIR}"
echo "目标目录：${DEST_DIR}"

if [ ! -f "${SRC_DIR}/pyproject.toml" ]; then
  echo "错误：${SRC_DIR} 下没有 pyproject.toml，请确认源目录是否正确。" >&2
  exit 1
fi

# ---- 1. 同步仓库到目标目录 ------------------------------------------------
mkdir -p "$DEST_DIR"

if command -v rsync >/dev/null 2>&1; then
  echo "使用 rsync 同步（排除 .git/.venv/dist 等）"
  rsync -a --delete \
    --exclude '.git' \
    --exclude '.venv' \
    --exclude 'dist' \
    --exclude 'build' \
    --exclude '__pycache__' \
    --exclude '.mypy_cache' \
    --exclude '.ruff_cache' \
    --exclude '.pytest_cache' \
    --exclude 'htmlcov' \
    "${SRC_DIR}/" "${DEST_DIR}/"
else
  echo "未找到 rsync，回退为 cp -R 复制关键内容"
  for item in pyproject.toml README.md LICENSE src tests docs scripts examples memory; do
    if [ -e "${SRC_DIR}/${item}" ]; then
      rm -rf "${DEST_DIR:?}/${item}"
      cp -R "${SRC_DIR}/${item}" "${DEST_DIR}/"
    fi
  done
fi

# ---- 2. 创建虚拟环境并安装 ------------------------------------------------
VENV_DIR="${DEST_DIR}/.venv"
if [ -x "${VENV_DIR}/bin/python" ]; then
  echo "已存在虚拟环境：${VENV_DIR}（复用）"
else
  echo "创建虚拟环境：${VENV_DIR}"
  python3 -m venv "$VENV_DIR"
fi

VPY="${VENV_DIR}/bin/python"
echo "升级 pip 并安装项目"
"$VPY" -m pip install --upgrade pip
"$VPY" -m pip install "${DEST_DIR}"

# ---- 3. 生成 systemd user unit 模板 ---------------------------------------
DEPLOY_DIR="${DEST_DIR}/deploy"
mkdir -p "$DEPLOY_DIR"
UNIT_FILE="${DEPLOY_DIR}/dwrg.service"

cat > "$UNIT_FILE" <<EOF
# DWRG CLI —— systemd user unit 模板（示例）
#
# 用途说明：
#   dwrg 是交互式命令行工具，正常使用方式是登录后在终端里直接执行，
#   例如：${VENV_DIR}/bin/dwrg --help
#   它不是一个常驻后台进程，所以这里用 Type=oneshot 描述「跑一次就退出」的
#   一次性任务（比如定时校验/更新客户端资源），而不是长期运行的服务。
#
# 如果确实需要常驻，请自行改为 Type=simple，并把 ExecStart 指向一个
#   真正会长期运行的子命令（本模板不假设存在这样一个子命令）。
#
# 安装为用户级 unit：
#   mkdir -p ~/.config/systemd/user
#   cp ${UNIT_FILE} ~/.config/systemd/user/dwrg.service
#   systemctl --user daemon-reload
#   systemctl --user start dwrg.service        # 手动触发一次
#   systemctl --user status dwrg.service
# 若希望开机自启（oneshot 场景通常不需要）：
#   systemctl --user enable dwrg.service
# 注意：user manager 需在登录会话中存在；服务器上可执行
#   loginctl enable-linger \$USER

[Unit]
Description=DWRG CLI 一次性任务（示例）
Documentation=file://${DEST_DIR}/README.md
After=network-online.target
Wants=network-online.target

[Service]
# oneshot：任务执行完即结束，符合交互式 CLI 的定位
Type=oneshot
RemainAfterExit=no
WorkingDirectory=${DEST_DIR}
# 示例命令：仅打印帮助，请替换为你的真实子命令，例如 resource check
ExecStart=${VENV_DIR}/bin/dwrg --help
# 如需日志落盘，可放开下面两行
# StandardOutput=append:${DEST_DIR}/dwrg.log
# StandardError=append:${DEST_DIR}/dwrg.log

[Install]
WantedBy=default.target
EOF

echo "已生成 systemd unit 模板：${UNIT_FILE}"

# ---- 4. 打印后续步骤 -------------------------------------------------------
echo ""
echo "安装完成 ✅"
echo "可执行文件：${VENV_DIR}/bin/dwrg"
echo ""
echo "下一步："
echo "  1) 试运行：${VENV_DIR}/bin/dwrg --help"
echo "  2) 部署 unit："
echo "       mkdir -p ~/.config/systemd/user"
echo "       cp ${UNIT_FILE} ~/.config/systemd/user/dwrg.service"
echo "       systemctl --user daemon-reload"
echo "       systemctl --user start dwrg.service"
echo "  3) 按需编辑 unit 中的 ExecStart（把 --help 换成真实的子命令）"
