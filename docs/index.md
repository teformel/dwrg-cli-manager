# 第五人格命令行管理器

一个面向**多渠道服 / 多账号**场景的第五人格命令行管理工具，命令名为 `dwrg`。

基于 Python 3.10+ 构建，采用 Typer + Rich + Pydantic V2，覆盖账号、渠道服、资源、启动、配置与插件六类能力，并提供系统诊断与状态检查。

## 特性

| 能力 | 说明 |
|------|------|
| 多渠道服管理 | 内置 `official` / `bserver` / `test_server` 渠道服，支持新增、删除、切换、设默认与并发延迟探测 |
| 多账号管理 | 账号创建、列出、切换、删除、登录/登出，密码同时以密文与哈希两种形式持久化 |
| 资源管理 | 基于清单的完整性检查、增量更新、缓存统计与清理，支持并发与断点续传 |
| 启动管理 | 解析游戏路径、组装启动命令与子进程环境、停止进程、查询运行状态 |
| 配置管理 | YAML / JSON 双格式配置，支持查看、设置、重置、导出与导入 |
| 插件系统 | 从插件目录动态加载 `Plugin` 子类，支持启用 / 禁用与状态持久化 |
| 国际化 | 9 种语言代码、扁平点号键目录、日期时间与时长本地化 |
| 安全 | Fernet 对称加密 + 密钥文件（`0600`）、PBKDF2-HMAC-SHA256 密码哈希、集中式输入校验 |
| 可观测性 | Rich 表格 / 面板输出、`--format json` 机器可读输出、滚动文件日志、`diagnose` 系统诊断 |

## 30 秒上手

安装（以 pipx 为例）：

```bash
pipx install dwrg-cli-manager
```

确认版本与命令树：

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

添加一个账号并查看当前状态：

```bash
dwrg account add --username tester --server official --password secret123
```

```text
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

> 说明：`--password` 是交互式隐藏输入项，命令行中直接书写仅为演示；实际使用时省略该参数会以隐藏提示方式录入。

## 命令总览

| 命令 | 作用 | 子命令 |
|------|------|--------|
| `dwrg help` | 显示命令总览 | — |
| `dwrg diagnose` | 系统诊断：环境、配置与启动条件 | — |
| `dwrg status` | 显示渠道服、账号与游戏运行状态 | — |
| `dwrg account` | 账号管理 | `add` `list` `switch` `remove` `status` `login` `logout` |
| `dwrg server` | 渠道服管理 | `list` `current` `detect` `switch` `show` `info` `add` `remove` `set-default` |
| `dwrg resource` | 资源管理 | `check` `verify` `update` `clean` `info` |
| `dwrg launch` | 启动管理 | `start` `stop` `status`（不带子命令时等同 `start`） |
| `dwrg config` | 配置管理 | `show` `set` `unset` `reset` `export` `import` |
| `dwrg plugin` | 插件管理 | `list` `info` `enable` `disable` |

全局选项：`--version / -V`、`--verbose / -v`、`--lang`。

完整的语法、选项、参数、示例与退出码见 [CLI 命令参考](cli-reference.md)。

## 目录导航

| 文档 | 内容 |
|------|------|
| [开始使用](getting-started.md) | 三种安装方式、首次运行与验证、卸载、常见问题 |
| [CLI 命令参考](cli-reference.md) | 逐个命令的语法、选项、参数、示例与退出码 |
| [配置](configuration.md) | 配置文件位置、格式、完整配置项表、环境变量 |
| [架构设计](architecture.md) | 分层架构、模块职责、数据流、关键设计决策 |
| [安全](security.md) | 密钥管理、密码哈希、加密与哈希分工、输入校验、威胁模型 |
| [国际化](i18n.md) | 语言切换、目录结构、`t()` 用法、新增语言步骤 |
| [插件系统](plugins.md) | 目录结构、`Plugin` 生命周期、元数据、开发示例 |
| [资源管理](resources.md) | 下载 / 校验 / 补丁流程、缓存目录、并发与断点续传 |
| [常见问题排查](troubleshooting.md) | 常见错误信息 → 原因 → 解决 |
| [开发指南](development.md) | 开发环境、质量命令、提交规范、如何新增命令 |
| [更新日志](changelog.md) | Keep a Changelog 格式 |

## 相关链接

- 贡献指南：见仓库根目录 `CONTRIBUTING.md`
- 项目结构：见仓库根目录 `PROJECT_STRUCTURE.md`
