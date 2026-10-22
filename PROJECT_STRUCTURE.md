# 项目结构说明

> 本文件描述**当前仓库的真实结构**。修改目录后请同步更新。
> 最后校准：2026-10-16（新增 checkout / transports / session / updater 等模块）。

## 目录结构

```
dwrg-cli-manager/
├── src/dwrg_manager/               # 源码（唯一的包根）
│   ├── __init__.py                 # 版本号、作者、惰性 get_app()
│   ├── main.py                     # 入口薄壳，仅再导出 cli.app
│   ├── cli.py                      # 全部 Typer 命令定义（单 app + 子 app）
│   ├── exceptions.py               # DWRGError 及 8 个子类
│   ├── config/                     # 配置管理
│   │   ├── models.py               # Config / AppConfig / ServerConfig / AccountConfig
│   │   └── manager.py              # ConfigManager（原子写入 YAML/JSON）
│   ├── accounts/                   # 账号管理
│   │   ├── models.py               # Account / LoginResult（运行时视图）
│   │   ├── session.py              # 登录态读写（session.json，0600）
│   │   ├── transfer.py             # 加密导出 / 导入账号
│   │   ├── gacha.py                # 扫描日志提取抽卡记录链接
│   │   └── manager.py              # AccountManager（CRUD / 切换 / 认证）
│   ├── servers/                    # 渠道服管理
│   │   ├── models.py               # ServerStatus / ServerManagerConfig（ServerConfig 再导出）
│   │   ├── detection.py            # 渠道服探测的辅助入口
│   │   ├── checkout.py             # ChannelSwitcher：秒级切换 / sync / download
│   │   │                           #   + 差异缓存与渠道配置备份
│   │   └── manager.py              # ServerManager（同步 CRUD + 异步探测）
│   ├── resources/                  # 资源管理
│   │   ├── models.py               # 资源清单与校验结果模型
│   │   ├── transports.py            # HttpIndexTransport / LocalIndexTransport
│   │   ├── downloader.py           # 并发下载 + 断点续传
│   │   ├── validator.py            # MD5 / 大小校验
│   │   ├── patcher.py              # 渠道服差异文件应用
│   │   └── manager.py              # ResourceManager
│   ├── launcher/                   # 启动管理
│   │   ├── models.py               # LaunchConfig / LaunchResult / GameStatus
│   │   └── manager.py              # LauncherManager（启动 / 停止 / 诊断）
│   ├── plugins/                    # 插件系统
│   │   ├── models.py               # 插件元数据
│   │   ├── base.py                 # Plugin 基类与生命周期钩子
│   │   └── manager.py              # PluginManager（发现 / 启用 / 禁用）
│   ├── i18n/                       # 国际化
│   │   ├── translator.py           # Translator / t()
│   │   ├── datetime_utils.py       # 本地化日期时间
│   │   └── locales/                # zh-CN.json / en-US.json
│   ├── security/                   # 安全（加密与校验的唯一实现处）
│   │   ├── crypto.py               # Fernet 密钥管理 + PBKDF2 密码哈希
│   │   └── validation.py           # validate_username / validate_password 等
│   └── utils/                      # 通用工具
│       ├── atomic.py               # atomic_write_text（临时文件 + os.replace + chmod）
│       ├── updater.py              # 版本检查与升级提示（PyPI）
│       ├── logger.py               # setup_logging / get_logger（stdlib logging）
│       ├── system.py               # SystemManager（系统 / 磁盘 / 进程信息）
│       ├── network.py              # fetch_json / ping_server / check_server_status
│       ├── version.py              # get_version()，惰性转发包根 __version__
│       ├── config.py               # load_config / save_config（向后兼容垫片）
│       ├── crypto.py               # 向后兼容再导出 → security.crypto
│       └── security.py             # 向后兼容再导出 → security.validation
├── tests/                          # 测试
│   ├── conftest.py                 # 隔离 HOME / 密钥 / 配置的公共 fixture
│   ├── README.md                   # 如何跑测试
│   ├── unit/                       # 单元测试（14 个测试文件，逐一对应源码模块）
│   ├── integration/                # 端到端 CLI 流程
│   └── performance/                # 导入耗时与规模测试（标 slow）
├── docs/                           # MkDocs Material 文档（12 篇）
│   ├── index.md                    # 简介与命令总览
│   ├── getting-started.md          # 安装与首次运行
│   ├── cli-reference.md            # 逐命令语法 / 选项 / 示例 / 退出码
│   ├── configuration.md            # 配置项表与环境变量
│   ├── architecture.md             # 分层架构与设计决策
│   ├── security.md                 # 密钥、哈希、校验规则、威胁模型
│   ├── i18n.md                     # 多语言机制
│   ├── plugins.md                  # 插件开发
│   ├── resources.md                # 资源下载 / 校验 / 打补丁
│   ├── troubleshooting.md          # 错误信息速查
│   ├── development.md              # 开发环境与质量命令
│   └── changelog.md                # 版本变更记录
├── examples/
│   └── basic_usage.py              # 以库形式调用三个管理器的可运行示例
├── scripts/                        # 辅助脚本
│   ├── setup.sh / setup.ps1        # 创建 venv 并安装 .[dev]
│   ├── check.sh                    # 本地质量门（fmt-check + lint + type + test）
│   ├── test.sh                     # 跑测试，支持 --unit / --integration / --fast
│   ├── build.sh                    # 构建 sdist + wheel
│   ├── release.sh                  # 发布前校验（版本号、tag、twine check）
│   ├── install-remote.sh           # 远程/容器内一键部署
│   └── README.md                   # 脚本用法
├── memory/                         # 项目规范文档（vibe-coding / testing / ci-cd 等）
├── .github/workflows/              # ci.yml / release.yml / codeql.yml
├── .archive/legacy-tests/          # 重构前的遗留脚本式测试（不参与 pytest 收集）
├── .pre-commit-config.yaml         # ruff / mypy / 基础 hooks
├── Makefile                        # make help / check / test / build / clean 等
├── mkdocs.yml                      # 文档站点配置
├── pyproject.toml                  # 依赖、构建、ruff、mypy、pytest、coverage 配置（唯一权威）
├── requirements.txt                # 仅为 `pip install -r` 提供的 `-e .[dev]` 指针
├── README.md                       # 项目说明与快速开始
├── CONTRIBUTING.md                 # 贡献指南
├── PROJECT_STRUCTURE.md            # 本文件
├── LICENSE                         # MIT
└── .gitignore / .zcodeignore       # 版本控制与编辑器忽略规则
```

## 核心模块说明

### 1. 入口层

- **`main.py`**：只有一行有效代码 —— `from .cli import app`。真正的入口薄壳，
  不含任何逻辑，避免 `python -m dwrg_manager.main` 与 console script 走两条路径。
- **`cli.py`**：唯一的 Typer `app` 定义处，挂载 `account` / `server` / `resource` /
  `launch` / `config` / `plugin` 六个子 app 以及 `help` / `diagnose` / `status` 三个顶层命令。
  用户可见的输出全部由 Rich 负责，日志走 stderr（`setup_logging(console=False)`）。

### 2. 领域模块

| 模块 | 职责 | 关键类 |
|---|---|---|
| `config/` | 配置的持久化与业务级 CRUD；YAML/JSON 双格式；原子写入 | `ConfigManager` |
| `accounts/` | 账号 CRUD、切换、密码校验与登录态 | `AccountManager` |
| `servers/` | 渠道服 CRUD 与异步状态探测 | `ServerManager` |
| `resources/` | 资源清单下载、完整性校验、渠道服差异应用 | `ResourceManager` |
| `launcher/` | 游戏客户端启动、停止、启动前诊断 | `LauncherManager` |
| `plugins/` | 第三方插件发现与生命周期管理 | `PluginManager` |

### 3. 支撑模块

- **`security/`**：加密与输入校验的**唯一实现处**。
  `crypto.py` 负责 Fernet 密钥（`~/.dwrg/keyfile`，0600）与 PBKDF2-HMAC-SHA256 密码哈希；
  `validation.py` 收敛全部输入校验规则。
  `src/dwrg_manager/utils/crypto.py` 与 `utils/security.py` 只是向后兼容的再导出，
  不要在新代码里用。
- **`i18n/`**：`translator.py` 提供 `t()` 与语言切换，locale 是普通 JSON，
  新增语言只需加一个文件并在 `SUPPORTED_LANGUAGES` 中登记。
- **`utils/`**：无领域知识的通用能力。日志用标准库 `logging`（不引入 loguru），
  网络用 `aiohttp`，系统信息用 `psutil`。
- **`exceptions.py`**：`DWRGError` 基类 + `ConfigError` / `AccountError` / `ServerError` /
  `ResourceError` / `LaunchError` / `PluginError` / `SecurityError` / `ValidationError`。
  每个异常都能给出 `user_message()`，CLI 层统一把它渲染给用户。

## 数据模型的两条重要约定

1. **`ServerConfig` 只有一个定义**，位于
   `src/dwrg_manager/config/models.py`；`src/dwrg_manager/servers/models.py`
   仅做再导出。历史上这两个文件各有一份字段不一致的定义，是当时最严重的坑。
2. **`AccountConfig`（持久化）与 `Account`（运行时）是两种东西**。
   前者含 `encrypted_password` / `password_hash`，后者是去掉密钥材料后的业务视图。
   转换由 `AccountManager._to_account()` 完成。

## 测试结构

- **`tests/unit/`**：与 `src/dwrg_manager` 下的模块一一对应，覆盖正常 / 边界 / 异常路径，
  异常统一用 `pytest.raises` 断言具体类型。全部标 `@pytest.mark.unit`。
  其中 `test_checkout.py` 专门覆盖秒级切换：首次切换建缓存、二次切换走缓存
  不触网、缓存损坏回落下载、大版本变化重置缓存、`sync` 四种状态、
  目录穿越防护等；下载器通过注入不触网的假代身驱动。
- **`tests/integration/`**：以 `CliRunner` 跑完整命令序列（建配置 → 加渠道服 → 加账号 →
  切换 → 导出 / 导入 → status），标 `@pytest.mark.integration`。
- **`tests/performance/`**：导入耗时预算与大量渠道服下的列表规模，标
  `@pytest.mark.performance` + `@pytest.mark.slow`。
- `tests/conftest.py` 会把 `HOME` / `USERPROFILE` / `XDG_CONFIG_HOME` / `DWRG_KEY_FILE`
  全部重定向到 `tmp_path`，**测试不会污染真实的 `~/.config/dwrg` 与 `~/.dwrg`**。

## 设计原则

1. **模块化**：每个子包只依赖它下层的模块，禁止 `utils` 反向依赖领域模块。
2. **可扩展**：渠道服、语言、插件都是数据驱动的，新增不需要改核心代码。
3. **用户友好**：命令与选项有中文帮助文本；错误信息带 `可用: a, b, c` 这类可执行提示。
4. **安全可靠**：敏感信息加密落盘；所有外部输入先过
   `src/dwrg_manager/security/validation.py`；
   配置文件采用「临时文件 + `os.replace`」原子写入。
