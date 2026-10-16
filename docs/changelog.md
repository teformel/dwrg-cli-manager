# 更新日志

本文件记录本项目的所有重要变更。

格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增

#### 秒级渠道服切换

- 新增顶层命令 `dwrg checkout <server>`、`dwrg sync`、`dwrg download <server>`，
  对标 `wutheringwaves-cli-manager` 的 `ww checkout` / `ww sync` / `ww download` 三件套。
- 差异缓存机制：首次切换把当前渠道服文件快照进
  `<game_dir>/dwrg_server_diff_cache/<server>/`，之后任意切换优先从本地缓存恢复。
- 大版本变化（`version` 文件内容改变）自动重置缓存。
- 切换前备份渠道配置文件（`dwrg_server_config_backup/`），失败即中止，
  不留中间态。
- `ChannelSwitcher` 新墟 `detect_current_server` / `rollback` / `cache_info` / `reset_cache` 能力。

#### 资源管理

- 新增 `dwrg resource index <DIR>`：扫描本地目录生成清单（path / size / md5），
  默认写入 `<DIR>/manifest.json`（原子写入）。
- 新增 `HttpIndexTransport` / `LocalIndexTransport`。
- 删除编造的 `resources.identityv.com` 资源源，资源源改为从
  `AppConfig.resource_sources` 读取（默认为已实测的国际服直链）。
- `resource check` / `verify` / `update` 新墟 `--dir` 与 `--source local|http|auto` 选项。

#### 账号管理

- 新增 `dwrg account export` / `dwrg account import`：Fernet 加密导出上下文，
  import 重失误时全量校验后再逐条应用。
- 新增登录态（`~/.dwrg/session.json`，0600）；`launch` 在启动配置未显式
  指定账号 / 渠道服时自动注入。
- 新增 `dwrg gacha` / `dwrg gacha scan`：扫描游戏日志提取抽卡记录链接，
  支持 `-o/--open` 打开浏览器；日志加密时给出提示而非报错。

#### 启动与可观测性

- 新增 `dwrg self-update`（`--check` 仅检查）：后台查询 PyPI，离线静默失败。
- `launch` 新墟 `--dry-run`：只打印将执行的命令行、环境变量与工作目录。
- `launch` 新墟 `--graphics <hd|sd|uhd>` 画质档位参数。
- `diagnose` 新墟检查项：游戏目录可写性、磁盘空间、密钥文件权限（0600）、
  渠道服配置完整性、资源源可达性（HEAD 探测，失败仅告警）。
- `status` 补充游戏进程探测（PID / 进程名 / 运行时长）。

### 修复

- `validate_path` 在提供 `base` 时将相对路径以 `base` 为根解析，而不是按进程
  CWD 解析；修复了 `dwrg sync` 把清单里的 `IdentityV.exe` 误判为路径越界、
  导致全部文件被跳过的问题。
- `dwrg diagnose` 的懒加载相对导入修正为单点导入（`cli.py` 位于包根，
  `..` 超出顶层包会抛 `ImportError`）。
- `ChannelSwitcher` 的 `_downloader` 属性与方法重名冲突（导致 mypy 报
  `method-assign`）重命名为 `_downloader_ref`。

### 变更

- ruff 新墟 `extend-exclude = [".archive"]`；该目录是重构前的遗留脚本式测试，
  不参与 pytest 收集，因此也不再计入 lint。

## [1.0.0] - 2026-10-03

首个完整版本，一次性交付全部核心能力。命令名 `dwrg`，包名 `dwrg-cli-manager`，要求 Python 3.10+。

### 新增

#### 命令行

- 顶层命令：`help`、`diagnose`、`status`，以及 `account` / `server` / `resource` / `launch` / `config` / `plugin` 六个子命令组。
- 全局选项：`--version/-V`、`--verbose/-v`、`--lang`。
- 统一输出约定：成功 `✓`、警告 `!`、失败 `✗`；`--format json` 提供机器可读输出。

#### 账号管理

- `account add / list / switch / remove / status / login / logout`。
- 账号密码以**密文**（Fernet）+ **哈希**（PBKDF2-HMAC-SHA256，100 000 次迭代）两种形式持久化。
- 输入校验：用户名 3–20 位 `[A-Za-z0-9_]`，密码 6–128 位且非全空白，账号 ID 长度 ≥ 8。

#### 渠道服管理

- `server list / current / detect / switch / show / info / add / remove / set-default`。
- 内置 `official` / `bserver` / `test_server` 三个渠道服。
- 异步并发探测延迟与在线状态，失败降级为 `offline`/`inactive` 而非抛异常。

#### 资源管理

- `resource check / verify / update / clean / info`。
- 基于清单的增量更新：以 `path` 为身份标识比对新增 / 更新 / 未变化 / 删除。
- 并发下载（信号量限流）、指数退避重试（最多 3 次）、基于 HTTP `Range` 的断点续传。
- 校验器支持分块流式哈希、整文件 MD5/SHA256 校验与抽样快速校验。
- 配置文件与本地清单采用「临时文件 + 原子替换」写入。

#### 启动管理

- `launch`（等同 `start`）/ `stop` / `status`。
- 游戏路径解析优先级：显式路径 → `DWRG_GAME_PATH` → 平台默认安装位置。
- 启动环境注入 `DWRG_LAUNCHED` / `DWRG_ACCOUNT` / `DWRG_SERVER`。

#### 配置管理

- `config show / set / unset / reset / export / import`。
- 默认配置 `~/.config/dwrg/config.yaml`，支持 YAML 与 JSON（按扩展名）。
- 首次运行自动创建预置渠道服的初始配置。

#### 插件系统

- 插件目录（默认 `~/.dwrg/plugins`）动态加载，支持目录布局（`<name>/plugin.py`）与单文件布局（`<name>.py`）。
- `Plugin` 基类生命周期 `on_load` / `on_enable` / `on_disable`；`PluginContext` 提供配置与日志最小接口。
- `plugin list / info / enable / disable`；启用状态持久化于 `plugins.json`。

#### 国际化

- 9 种语言代码支持，扁平点号键目录（`locales/<lang>.json`）。
- 回退链：精确语言 → 同语系基础语言 → `zh-CN` → `default` → 键名。
- 日期、时间、时长与相对时间的本地化格式化（纯标准库实现）。

#### 安全

- `security` 包作为加密与校验的**唯一实现来源**；`utils.crypto` / `utils.security` 保留为兼容再导出层。
- Fernet 密钥文件默认 `~/.dwrg/keyfile`，权限 `0600`，跨进程复用；支持 `DWRG_ENCRYPTION_KEY` / `DWRG_KEY_FILE` 覆盖。
- `validate_path` 提供目录穿越防护。
- 统一异常体系 `DWRGError` 及 8 个子类，CLI 层统一转换为用户可读信息。

#### 工具与可观测性

- 标准库 `logging` 日志，滚动文件 `~/.dwrg/logs/dwrg.log`（5 MiB × 5）。
- 系统诊断 `diagnose`，可导出 JSON 报告。
- `utils.network` 提供渠道服探测所需的异步 HTTP 能力并统一包装为 `ServerError`。

### 变更

- `ServerConfig` 收敛为单一定义（`config/models.py`），`servers/models.py` 改为再导出，消除了重复定义。
- 版本号唯一来源为包根 `__version__`，`utils/version.py` 改为惰性转发。
- 加密能力由 `utils` 迁移至 `security` 包。

### 修复

- 修复账号密码在重启后无法解密的问题（密钥改为落盘复用）。
- 修复校验密码时引用不存在 `password_hash` 字段的问题。
- 修复配置写入中断可能损坏文件的问题（改为原子写入）。

### 说明

- 本版本日期为文档基线日期，正式发布时以仓库标签为准。
