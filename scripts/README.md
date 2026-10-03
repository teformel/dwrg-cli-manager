# scripts 目录说明

本目录存放项目开发 / 构建 / 发布 / 部署相关脚本。
约定：POSIX shell 脚本一律 `#!/usr/bin/env sh` + `set -eu`，保证在 Linux、WSL、macOS 与 Git Bash 上可用；
Windows 原生环境提供 `.ps1` 版本（兼容 Windows PowerShell 5.1）。

| 脚本 | 平台 | 作用（一句话） |
| --- | --- | --- |
| `setup.sh` | POSIX sh | 检测 Python ≥ 3.10、创建 `.venv`、升级 pip、安装 `.[dev]`，幂等可重复执行。 |
| `setup.ps1` | Windows PS 5.1 | 与 `setup.sh` 等价的 Windows 版本（UTF-8 输出）。 |
| `check.sh` | POSIX sh | 本地质量门禁：格式检查 → lint → 类型检查 → 测试，任一步失败即非 0 退出。 |
| `test.sh` | POSIX sh | 运行测试并把参数透传给 pytest，支持 `--unit` / `--integration` / `--fast`。 |
| `build.sh` | POSIX sh | 清理后构建 sdist + wheel，打印产物清单与 sha256 校验和。 |
| `release.sh` | POSIX sh | 发布前校验：工作区干净、HEAD 在 tag 上、版本一致、`twine check`（dry-run 不上传）。 |
| `install-remote.sh` | POSIX sh | 远程/容器一次性部署：同步仓库、建 venv、装包、生成 systemd user unit 模板。 |

## 用法示例

### 1. 初始化开发环境

```sh
# Linux / WSL / macOS / Git Bash
sh scripts/setup.sh
. .venv/bin/activate
```

```powershell
# Windows PowerShell 5.1
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
.\scripts\setup.ps1 -PythonExe python3.12   # 指定解释器
.\scripts\setup.ps1 -VenvDir .venv312       # 指定虚拟环境目录
```

### 2. 质量门禁

```sh
sh scripts/check.sh
# 等价于依次执行：
#   ruff format --check src
#   ruff check src
#   mypy src
#   pytest
```

### 3. 运行测试

```sh
sh scripts/test.sh                       # 全部测试（默认 tests/）
sh scripts/test.sh --unit                # 只跑 unit 标记
sh scripts/test.sh --integration         # 只跑 integration 标记
sh scripts/test.sh --fast                # 跳过 slow 标记
sh scripts/test.sh --fast -x -k login    # 其余参数原样透传给 pytest
sh scripts/test.sh tests/integration -k switch
```

### 4. 构建与校验发布包

```sh
sh scripts/build.sh                      # 生成 dist/*.tar.gz 与 dist/*.whl，并打印 sha256
sh scripts/release.sh                    # 需要先打 tag 且工作区干净
```

### 5. 远程 / 容器内部署

```sh
# 默认：源=仓库根，目标=$HOME/.local/share/dwrg-cli
sh scripts/install-remote.sh

# 显式指定源与目标
sh scripts/install-remote.sh /path/to/repo /opt/dwrg

# 仅指定目标目录
DEST_DIR=/srv/dwrg sh scripts/install-remote.sh
```

部署后会生成 `deploy/dwrg.service`（systemd user unit 模板，`Type=oneshot`，
因为 `dwrg` 是交互式 CLI，不是常驻服务），并打印启用步骤。

## 说明与注意

- 所有脚本都会自动定位仓库根目录，可在任意工作目录下用相对 / 绝对路径调用。
- `check.sh` / `test.sh` / 其它脚本会优先使用 `.venv` 内的解释器，找不到时回退到
  `python3` / `python`（可用环境变量 `PYTHON` 覆盖）。
- 需要管道失败即中止的脚本若改用 `bash`，请显式声明 `set -o pipefail`；
  本目录当前脚本均未依赖管道退出码，因此保持 `sh`。
- `release.sh` 只做校验，不会上传；真正上传请手动执行
  `python -m twine upload dist/*` 并确认目标仓库。
