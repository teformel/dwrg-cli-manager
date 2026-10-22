# 第五人格命令行管理器

<!-- 徽章占位：替换为你的仓库地址后即可生效 -->
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://img.shields.io/badge/ci-pending-lightgrey.svg)](#)
[![Coverage](https://img.shields.io/badge/coverage-pending-lightgrey.svg)](#)

> 一个用命令行管理第五人格多渠道服与多账号的工具，命令名为 `dwrg`。

<!-- 截图占位：将真实截图放入 docs/assets/ 后取消下一行注释 -->
<!-- ![dwrg help 界面](docs/assets/screenshot.png) -->

## 安装

```bash
# 推荐：pipx（隔离环境）
pipx install dwrg-cli-manager

# 或：uv
uv tool install dwrg-cli-manager

# 或：源码 + venv
git clone https://github.com/dwrg-team/dwrg-cli-manager.git
cd dwrg-cli-manager
python -m venv venv
source venv/bin/activate        # Windows：venv\Scripts\activate
pip install -e ".[dev]"
```

要求 Python 3.10 或更高版本。详见 [开始使用](docs/getting-started.md)。

## 快速开始

```bash
dwrg --version
```

```text
DWRG CLI Manager 1.0.0
```

```bash
dwrg help
```

```text
可用命令
 account   账号管理
 server    渠道服管理
 resource  资源管理
 launch    启动管理
 config    配置管理
 plugin    插件管理
 diagnose  系统诊断
 status    状态检查
```

```bash
dwrg account add --username tester --server official
```

```text
Password:
✓ 账号添加成功: tester (3f1c2ab9...)
```

```bash
dwrg status
```

```text
 项目          值
 版本          1.0.0
 配置文件      /home/<user>/.config/dwrg/config.yaml
 当前渠道服    official (1.0.0)
 当前账号      tester (3f1c2ab9...)
 渠道服数量    3
 账号数量      1
! 游戏未运行
```

## 特性

| 能力 | 说明 |
|------|------|
| 秒级渠道服切换 | `dwrg checkout` 利用 MD5 差异缓存实现切换：首次快照当前渠道服，之后任意切换从本地缓存恢复，不重下载整包；大版本变化自动重置缓存 |
| 全量校验与修复 | `dwrg sync` 对比差异缓存快照的 MD5，报告损坏 / 缺失，`--repair` 从缓存修复；`dwrg download` 从零下载客户端框架 |
| 本地资源索引 | `dwrg resource index <DIR>` 扫描目录生成清单（path / size / md5），原子写入；`HttpIndexTransport` 可用 HTTP ETag 当 MD5 作为补充源 |
| 多渠道服 | 内置 `official` / `bserver` / `test_server`，支持新增、删除、设默认与并发延迟探测 |
| 多账号 | 创建、列出、切换、删除、登录 / 登出、加密导出 / 导入；密码以密文 + 哈希双形式存储 |
| 启动管理 | 路径解析、启动前检查（磁盘空间 / 进程冲突 / 可执行文件）、`--dry-run` 演练、画质档位参数、进程停止与状态查询 |
| 抽卡记录 | `dwrg gacha` 扫描游戏日志提取记录链接，`-o/--open` 一键打开浏览器 |
| 自更新 | `dwrg self-update` 后台查询 PyPI 版本，离线静默不报错 |
| 配置管理 | YAML / JSON 双格式；查看、设置、重置、导出、导入；原子写入 |
| 插件系统 | 目录 / 单文件布局动态加载 `Plugin` 子类，启用状态持久化 |
| 国际化 | 9 种语言代码，点号键目录与回退链，日期时间本地化 |
| 安全 | Fernet 密钥文件（`0600`）、PBKDF2-HMAC-SHA256 哈希、集中式输入校验；所有缓存恢复经过 `validate_path` 防目录穿越 |
| 可观测性 | Rich 表格 / 面板、`--format json`、滚动日志、`diagnose` 诊断报告 |

## 命令总览

| 命令 | 子命令 |
|------|--------|
| `dwrg help` | — |
| `dwrg diagnose` | — |
| `dwrg status` | — |
| `dwrg self-update` | `--check` 仅检查版本 |
| `dwrg account` | `add` `list` `switch` `remove` `status` `login` `logout` `export` `import` |
| `dwrg server` | `list` `current` `detect` `switch` `show` `info` `add` `remove` `set-default` |
| `dwrg checkout` | `<server>` `--path/-p` `--force-sync` |
| `dwrg sync` | `--path/-p` `--repair` |
| `dwrg download` | `<server>` `--path/-p` |
| `dwrg resource` | `index` `check` `verify` `update` `clean` `info` |
| `dwrg launch` | `start` `stop` `status`（不带子命令时等同 `start`） |
| `dwrg config` | `show` `set` `unset` `reset` `export` `import` |
| `dwrg plugin` | `list` `info` `enable` `disable` |
| `dwrg gacha` | `scan`（不带子命令时等同 `scan`） |

全局选项：`--version/-V`、`--verbose/-v`、`--lang`。子命令普遍支持 `--config`（`plugin` 子命令用 `--plugin-dir`）。完整说明见 [CLI 命令参考](docs/cli-reference.md)。

## 文档索引

| 文档 | 内容 |
|------|------|
| [开始使用](docs/getting-started.md) | 安装、首次运行、验证、卸载、常见问题 |
| [CLI 命令参考](docs/cli-reference.md) | 逐个命令的语法、选项、参数、示例与退出码 |
| [配置](docs/configuration.md) | 配置位置、格式、完整配置项表、环境变量 |
| [架构设计](docs/architecture.md) | 分层架构、模块职责、数据流与设计决策 |
| [安全](docs/security.md) | 密钥管理、密码哈希、校验规则、威胁模型 |
| [国际化](docs/i18n.md) | 语言切换、目录结构、`t()` 用法、新增语言 |
| [插件系统](docs/plugins.md) | 目录结构、`Plugin` 生命周期、开发示例 |
| [资源管理](docs/resources.md) | 下载 / 校验 / 打补丁流程、缓存、并发与续传 |
| [常见问题排查](docs/troubleshooting.md) | 常见错误信息 → 原因 → 解决 |
| [开发指南](docs/development.md) | 开发环境、质量命令、提交规范、新增命令 |
| [更新日志](docs/changelog.md) | Keep a Changelog 格式 |

## 开发

```bash
uv sync

uv run ruff format .
uv run ruff check .
uv run mypy src/
uv run pytest
```

本地预览文档（需安装 `docs` 可选依赖）：

```bash
pip install -e ".[docs]"
mkdocs serve
```

贡献流程与代码规范见 [开发指南](docs/development.md)，行为准则见仓库根目录 `CONTRIBUTING.md`。

## 许可证

本项目采用 MIT 许可证，详见 [LICENSE](LICENSE)。
