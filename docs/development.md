# 开发指南

本页面向贡献者，说明开发环境、目录结构、质量命令、提交规范与扩展方式。

## 一、开发环境

### 1. 前置条件

| 工具 | 说明 |
|------|------|
| Python 3.10+ | 项目声明 `requires-python = ">=3.10"` |
| Git | 版本控制 |
| uv（推荐）或 venv + pip | 依赖管理 |

### 2. 初始化

```bash
git clone https://github.com/dwrg-team/dwrg-cli-manager.git
cd dwrg-cli-manager

# 方式一：uv
uv sync

# 方式二：venv + pip
python -m venv venv
source venv/bin/activate        # Linux / macOS
venv\Scripts\activate           # Windows
pip install -e ".[dev]"
```

开发依赖（`[project.optional-dependencies].dev`）包含：`ruff`、`mypy`、`pytest`、`pytest-asyncio`、`pytest-cov`、`black`、`pre-commit`、`bandit`、`safety`。

## 二、目录结构

```text
dwrg-cli-manager/
├── src/dwrg_manager/
│   ├── __init__.py          # 版本与作者元数据、get_app()
│   ├── main.py              # 控制台脚本入口
│   ├── cli.py               # Typer 应用与全部命令（唯一定义处）
│   ├── exceptions.py        # DWRGError 体系
│   ├── config/              # models.py（唯一数据模型）、manager.py
│   ├── accounts/            # manager.py、models.py
│   ├── servers/             # manager.py、models.py、detection.py
│   ├── resources/           # manager.py、downloader.py、validator.py、patcher.py、models.py
│   ├── launcher/            # manager.py、models.py
│   ├── plugins/             # base.py、manager.py、models.py
│   ├── i18n/                # translator.py、datetime_utils.py、locales/
│   ├── security/            # crypto.py、validation.py
│   └── utils/               # logger.py、network.py、system.py、version.py、config.py
├── tests/                   # 单元 / 集成 / 性能测试
├── docs/                    # 文档（MkDocs Material）
├── scripts/                 # 辅助脚本
├── examples/                # 使用示例
├── pyproject.toml
└── README.md
```

代码约定（`vibe-coding` 规范）：

- 使用 Python 3.10+ 类型注解，公共 API 必须有完整类型提示；
- 公共模块 / 类 / 函数必须有 Google 风格文档字符串；
- 具体异常类型，提供有意义的错误信息；
- 行长度 88，由 `ruff format` 保证。

## 三、质量命令

| 目的 | 命令 |
|------|------|
| 格式化 | `ruff format .` |
| 静态检查 | `ruff check .`（可加 `--fix` 自动修复） |
| 类型检查 | `mypy src/` |
| 测试 | `pytest` |
| 单文件测试 | `pytest tests/test_accounts.py` |
| 覆盖率 | `pytest --cov=src --cov-report=html` |
| 安全检查 | `bandit -r src/`、`safety check` |
| 提交前钩子 | `pre-commit run --all-files` |

使用 uv 时统一加前缀：

```bash
uv run ruff format .
uv run ruff check .
uv run mypy src/
uv run pytest
```

### 1. ruff 配置要点

```toml
[tool.ruff]
line-length = 88
target-version = "py310"
fix = true

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "ARG001"]
ignore = ["E501", "B008", "W191", "B904"]
```

### 2. mypy 配置要点

启用 `disallow_untyped_defs`、`disallow_incomplete_defs`、`check_untyped_defs`、`strict_equality` 等严格项，并为 `typer` / `rich` / `aiohttp` / `cryptography` / `psutil` / `yaml` 等第三方库设置 `ignore_missing_imports = true`。

### 3. pytest 配置要点

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["--strict-markers", "--strict-config", "--cov=src", "--cov-report=term-missing", "--cov-report=html", "--cov-report=xml"]
markers = ["unit", "integration", "e2e", "performance", "slow"]
```

## 四、提交规范

使用 Conventional Commits：

```text
<type>(<scope>): <subject>
```

| type | 含义 |
|------|------|
| `feat` | 新功能 |
| `fix` | 缺陷修复 |
| `docs` | 文档变更 |
| `refactor` | 重构（不改变外部行为） |
| `test` | 测试相关 |
| `perf` | 性能优化 |
| `chore` | 构建 / 工具 / 依赖 |

示例：

```bash
git checkout -b feature/account-management
git add .
git commit -m "feat(account): 支持按渠道服过滤账号列表"
git push origin feature/account-management
```

提交前清单：

- [ ] `ruff format .` 与 `ruff check .` 通过
- [ ] `mypy src/` 通过
- [ ] `pytest` 通过
- [ ] 涉及用户可见行为时同步更新 `docs/` 与 `CHANGELOG`
- [ ] 不提交密钥文件、真实账号或个人信息

## 五、如何新增命令

`cli.py` 是 Typer 应用的**唯一定义处**，`main.py` 只做入口转发。新增命令遵循以下步骤。

### 1.（可选）在业务层补充能力

优先把业务逻辑放进对应的 `Manager`，并抛出 `DWRGError` 子类：

```python
# src/dwrg_manager/accounts/manager.py
def count_accounts(self, server: str | None = None) -> int:
    """统计账号数量。

    Args:
        server: 仅统计该渠道服；为 None 时统计全部。

    Returns:
        账号数量。
    """
    return len(self.list_accounts(server))
```

### 2. 在 `cli.py` 定义命令

在对应子命令组上用装饰器注册；参数使用 `typer.Argument` / `typer.Option`；业务调用用 `_cli_errors` 包裹；输出用 `_ok` / `_warn` / `_fail` 与 `_table`。

```python
@account_app.command("count")
def account_count(
    server: str | None = typer.Option(None, "--server", "-s", help="渠道服"),
    fmt: str = typer.Option("table", "--format", "-f", help="输出格式: table | json"),
    config: str | None = typer.Option(None, "--config", help="自定义配置文件路径"),
) -> None:
    """统计账号数量。"""
    with _cli_errors("统计账号"):
        manager = AccountManager(ConfigManager(config) if config else ConfigManager())
        total = manager.count_accounts(server)
        if fmt == "json":
            _json_out({"total": total})
            return
        table = _table("渠道服", "账号数")
        table.add_row(server or "全部", str(total))
        console.print(table)
```

要点：

（1）子命令组统一使用 `no_args_is_help=True`（`launch` 组例外）；
（2）除 `plugin` 组外，所有子命令都应提供 `--config`；`plugin` 组使用 `--plugin-dir`；
（3）`--format` 统一取值 `table` / `json`；JSON 输出走 `_json_out`（直接写 stdout，不折行）；
（4）业务失败不要自行 `print` 后 `sys.exit`，交给 `_cli_errors` 统一处理；
（5）需要用户确认的操作使用 `typer.confirm`，并支持 `--force` / `-f` 跳过。

### 3. 补充多语言文案（可选）

若文案经 `t()` 输出，需在 `i18n/locales/` 的中文与英文目录中补键：

```json
{
  "cli.account.count.success": "共 {count} 个账号"
}
```

详见 [国际化](i18n.md#四新增语言步骤)。

### 4. 添加测试

```python
# tests/test_accounts.py
from typer.testing import CliRunner

from dwrg_manager.cli import app

runner = CliRunner()


def test_account_count_json(tmp_path):
    config_path = tmp_path / "config.yaml"
    result = runner.invoke(
        app, ["account", "count", "--config", str(config_path), "--format", "json"]
    )
    assert result.exit_code == 0
```

测试应通过 `--config` / `tmp_path` 指向临时配置文件，避免污染真实 `~/.config/dwrg/config.yaml`；异步逻辑可通过注入假 `transport` / `session_factory` 避开真实网络。
