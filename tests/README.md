# dwrg-manager 测试套件

本目录是「第五人格多渠道服/多账号命令行管理器」的 pytest 测试套件。所有
测试都做了进程级隔离，**不会读写真实的 `~/.config/dwrg` 与 `~/.dwrg`**。

## 目录结构

```
tests/
├── conftest.py                 # 隔离环境与公共 fixture
├── unit/                       # 单元测试
│   ├── test_config_models.py   # 配置数据模型
│   ├── test_config_manager.py  # 配置读写与 CRUD
│   ├── test_accounts.py        # 账号模型与管理器
│   ├── test_servers.py         # 渠道服模型与异步探测
│   ├── test_launcher.py        # 启动管理器（进程被 mock）
│   ├── test_security.py        # 加密与输入校验
│   ├── test_utils.py           # logger / system / version / network
│   └── test_cli.py             # Typer CLI 各命令分支
├── integration/                # 集成测试
│   └── test_cli_flows.py       # 端到端 CLI 工作流
└── performance/                # 性能冒烟测试
    └── test_startup.py         # 导入耗时与大批量渠道服查询
```

## 如何运行

在仓库根目录（`pyproject.toml` 所在处）执行：

```bash
# 全量测试（含覆盖率，按 pyproject 配置输出）
python -m pytest

# 只跑单元测试
python -m pytest tests/unit

# 只跑集成测试
python -m pytest tests/integration

# 跳过 slow 标记（默认会带上性能测试）
python -m pytest -m "not slow"

# 只跑性能测试
python -m pytest tests/performance -m "performance"

# 本地快速自检（不收集覆盖率）
python -m pytest tests -q --no-cov
```

若源码未安装到当前环境，可显式指定 `PYTHONPATH`：

```bash
PYTHONPATH=src python -m pytest tests -q --no-cov
```

## 测试标记（marker）

项目开启了 `--strict-markers`，只能使用以下标记：

| 标记           | 含义             |
| -------------- | ---------------- |
| `unit`         | 单元测试         |
| `integration`  | 集成测试         |
| `e2e`          | 端到端测试       |
| `performance`  | 性能测试         |
| `slow`         | 耗时较久的测试   |

## 隔离与 mock 约定

- `tests/conftest.py` 的 `isolated_environment`（`autouse`）会把 `HOME`、
  `USERPROFILE`、`XDG_CONFIG_HOME` 重定向到 `tmp_path`，并把密钥文件通过
  `DWRG_KEY_FILE` 指向临时目录，同时清空 `DWRG_ENCRYPTION_KEY`；
- 公共 fixture：`config_path` / `config_manager` / `account_manager` /
  `server_manager` / `cli_runner`；
- 所有网络访问（`ping_server`、`check_server_status`、`fetch_json`）与
  `subprocess.Popen` / `psutil.Process` 都被替换为测试替身，不依赖网络，
  也不会真正启动游戏进程；
- 异步测试直接写 `async def test_...`（项目 `asyncio_mode = "auto"`），
  无需 `@pytest.mark.asyncio`。

## 覆盖率

覆盖率目标 ≥ 80%。覆盖率相关阈值与报告格式由根目录 `pyproject.toml` 统一
配置，本测试目录不做任何修改。
