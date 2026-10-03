# 开始使用

本文介绍如何安装、首次运行、验证与卸载 `dwrg`。

## 一、前置条件

| 项目 | 要求 |
|------|------|
| Python | 3.10 或更高版本（`pyproject.toml` 声明 `requires-python = ">=3.10"`） |
| 操作系统 | 跨平台；`diagnose` 与启动路径探测对 Windows 有专门处理 |
| 网络 | 渠道服探测与资源下载需要网络，离线环境下相关命令会优雅降级 |

## 二、安装

### 1. 使用 pipx（推荐，隔离环境）

```bash
pipx install dwrg-cli-manager
```

安装后 `dwrg` 会加入 `PATH`，对应控制台脚本 `dwrg = "dwrg_manager.main:app"`。

### 2. 使用 uv

```bash
# 安装为独立的命令行工具
uv tool install dwrg-cli-manager

# 或不安装、直接运行
uvx --from dwrg-cli-manager dwrg --version
```

### 3. 源码 + venv

```bash
git clone https://github.com/dwrg-team/dwrg-cli-manager.git
cd dwrg-cli-manager

# 创建并激活虚拟环境
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows（PowerShell）

# 可编辑安装（含开发依赖）
pip install -e ".[dev]"
```

也可以使用 uv 管理源码环境：

```bash
uv sync
uv run dwrg --version
```

## 三、首次运行

### 1. 自动创建配置

首次执行任意命令时，若默认配置文件不存在，程序会自动写入一份预置了默认渠道服的初始配置：

```text
~/.config/dwrg/config.yaml
```

该文件包含 `app` / `servers` / `accounts` 三部分。默认渠道服为 `official`、`bserver`、`test_server`，其中 `official` 被标记为默认。

### 2. 查看命令树

```bash
dwrg help
```

`dwrg` 不带任何参数时同样会打印帮助（`no_args_is_help=True`）。

### 3. 查看初始状态

```bash
dwrg status
```

`status` 会展示版本、配置文件路径、当前渠道服、当前账号、渠道服与账号数量，并在最后检查本会话中的游戏进程状态。

### 4. 添加第一个账号

```bash
dwrg account add --username tester --server official
```

省略 `--password` 时会以隐藏输入方式提示录入密码：

```text
Password:
✓ 账号添加成功: tester (3f1c2ab9...)
```

> `--username` 与 `--password` 为必填项；`--server` 默认为 `official`。

## 四、验证安装

| 检查项 | 命令 | 预期 |
|--------|------|------|
| 版本 | `dwrg --version` | 输出 `DWRG CLI Manager <版本号>` |
| 命令树 | `dwrg help` | 打印可用命令面板 |
| 配置读写 | `dwrg config show` | 打印 `app.*` 配置项及渠道服 / 账号数量 |
| 系统环境 | `dwrg diagnose` | 打印系统与启动环境检查结果 |
| 运行状态 | `dwrg status` | 打印当前渠道服、账号与游戏运行状态 |

需要机器可读输出时，可为部分命令追加 `--format json`：

```bash
dwrg server list --format json
```

## 五、环境变量（可选）

| 变量 | 作用 |
|------|------|
| `DWRG_GAME_PATH` | 显式指定游戏可执行文件路径，优先于平台默认探测路径 |
| `DWRG_ENCRYPTION_KEY` | 直接提供 Fernet 密钥，或提供口令由 PBKDF2 派生 |
| `DWRG_KEY_FILE` | 自定义加密密钥文件路径（默认 `~/.dwrg/keyfile`） |

详见 [配置](configuration.md)。

## 六、卸载

```bash
# pipx
pipx uninstall dwrg-cli-manager

# uv tool
uv tool uninstall dwrg-cli-manager

# pip（源码 / venv 安装）
pip uninstall dwrg-cli-manager
```

如需一并清除本地数据，可手动删除以下目录（**含密钥与已保存的账号信息，请谨慎**）：

| 路径 | 内容 |
|------|------|
| `~/.config/dwrg/` | 配置文件 `config.yaml` |
| `~/.dwrg/` | 密钥文件、日志、插件目录、数据与缓存目录 |

## 七、常见问题

**Q：`dwrg: command not found`？**
安装后 `dwrg` 应位于当前 Python 环境的脚本目录中。若使用 venv，请先激活；若使用 pipx，请运行 `pipx ensurepath`。

**Q：提示「配置文件解析失败」？**
说明 `~/.config/dwrg/config.yaml` 内容非法。可参考 [常见问题排查](troubleshooting.md) 修复，或删除该文件后重新执行命令以重建默认配置。

**Q：命令输出中文出现乱码？**
确保终端使用 UTF-8 编码。`--format json` 的输出直接写入标准输出且不折行，可安全通过管道交给 `jq`。

**Q：游戏路径探测不到？**
设置 `DWRG_GAME_PATH` 指向可执行文件；`dwrg diagnose` 会列出探测结果与建议。
