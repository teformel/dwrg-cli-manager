# 配置

`dwrg` 的配置由 `ConfigManager` 统一读写，默认落盘为 YAML，也支持 JSON。本页说明配置文件位置、结构、完整配置项、`config` 命令用法与环境变量。

## 一、配置文件位置

| 场景 | 路径 |
|------|------|
| 默认 | `~/.config/dwrg/config.yaml` |
| 自定义 | 通过各子命令的 `--config <路径>` 指定（插件子命令除外） |

当默认文件不存在时，首次执行命令会**自动创建**一份初始配置：预置 `official` / `bserver` / `test_server` 三个渠道服（`official` 为默认），账号集合为空。

## 二、文件格式

格式由**文件扩展名**决定：

| 扩展名 | 解析 / 序列化方式 |
|--------|-------------------|
| `.json` | `json.loads` / `json.dump`（`indent=2`、`ensure_ascii=False`） |
| 其它（如 `.yaml` / `.yml`） | `yaml.safe_load` / `yaml.safe_dump`（`allow_unicode=True`） |

顶层必须是映射（对象），包含三个键：

| 顶层键 | 类型 | 说明 |
|--------|------|------|
| `app` | 对象 | 应用级配置（`AppConfig`） |
| `servers` | 对象 | 渠道服集合，键为渠道服名称 |
| `accounts` | 对象 | 账号集合，键为账号 ID |

### 1. YAML 示例

```yaml
app:
  server: official
  account: null
  auto_update: true
  verbose: false
  language: zh-CN
  data_dir: ~/.dwrg
  cache_dir: ~/.dwrg/cache
  log_level: INFO
  max_concurrent_downloads: 5
  download_timeout: 300
servers:
  official:
    name: official
    endpoint: https://idv.163.com
    region: CN
    status: active
    version: 1.0.0
    is_default: true
    last_check: null
    ping: null
    players: null
  bserver:
    name: bserver
    endpoint: https://game.bilibili.com/idv
    region: CN
    status: active
    version: 1.0.0
    is_default: false
    last_check: null
    ping: null
    players: null
  test_server:
    name: test_server
    endpoint: https://test.idv.163.com
    region: CN
    status: active
    version: 1.0.0
    is_default: false
    last_check: null
    ping: null
    players: null
accounts: {}
```

### 2. JSON 示例

```json
{
  "app": { "server": "official", "language": "zh-CN" },
  "servers": {},
  "accounts": {}
}
```

> `Config` 使用 Pydantic 的宽松解析：缺省字段会自动补齐默认值，因此手写的配置文件不必列全所有键。

## 三、完整配置项

### 1. 应用级配置 `app`（`AppConfig`）

| 键 | 类型 | 默认值 | 取值范围 | 说明 |
|----|------|--------|----------|------|
| `server` | `str` | `official` | 已存在的渠道服名称 | 当前渠道服 |
| `account` | `str \| null` | `null` | 已存在的账号 ID | 当前账号 |
| `auto_update` | `bool` | `true` | `true` / `false` | 是否自动更新 |
| `verbose` | `bool` | `false` | `true` / `false` | 是否详细输出 |
| `language` | `str` | `zh-CN` | 见 `SUPPORTED_LANGUAGES` | 输出语言 |
| `data_dir` | `str` | `~/.dwrg` | 任意路径 | 数据目录（游戏目录 = `data_dir/game`） |
| `cache_dir` | `str` | `~/.dwrg/cache` | 任意路径 | 缓存目录 |
| `log_level` | `str` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` | 日志级别（自动大写） |
| `max_concurrent_downloads` | `int` | `5` | `1`–`10` | 最大并发下载数 |
| `download_timeout` | `int` | `300` | `5`–`3600` | 单次下载总超时（秒） |

受支持语言共 9 种：

```text
zh-CN  zh-TW  en-US  ja-JP  ko-KR  fr-FR  de-DE  es-ES  ru-RU
```

### 2. 渠道服配置 `servers`（`ServerConfig`）

`ServerConfig` 的唯一定义位于 `dwrg_manager.config.models`，`dwrg_manager.servers` 仅做再导出。

| 字段 | 类型 | 默认值 | 取值范围 | 说明 |
|------|------|--------|----------|------|
| `name` | `str` | —（必填） | `^[A-Za-z0-9_-]+$` | 渠道服唯一名称 |
| `endpoint` | `str` | `""` | — | 接口地址 |
| `region` | `str` | `CN` | — | 地区 |
| `status` | `str` | `active` | `active` / `inactive` / `maintenance` | 渠道服状态 |
| `version` | `str` | `1.0.0` | — | 客户端版本号 |
| `is_default` | `bool` | `false` | `true` / `false` | 是否为默认渠道服 |
| `last_check` | `datetime \| null` | `null` | ISO 8601 | 最近探测时间 |
| `ping` | `float \| null` | `null` | 毫秒 | 最近探测延迟 |
| `players` | `int \| null` | `null` | — | 最近探测在线玩家数 |

内置渠道服定义：

| 名称 | 接口地址 | 地区 |
|------|----------|------|
| `official` | `https://idv.163.com` | `CN` |
| `bserver` | `https://game.bilibili.com/idv` | `CN` |
| `test_server` | `https://test.idv.163.com` | `CN` |

### 3. 账号配置 `accounts`（`AccountConfig`，持久化形态）

| 字段 | 类型 | 默认值 | 约束 | 说明 |
|------|------|--------|------|------|
| `id` | `str` | —（必填） | 长度 ≥ 8 | 账号 ID（UUID） |
| `username` | `str` | —（必填） | 3–20 位，`[A-Za-z0-9_]` | 用户名 |
| `server` | `str` | —（必填） | 渠道服名称规范 | 所属渠道服 |
| `encrypted_password` | `str` | `""` | — | 应用密钥加密后的密码密文 |
| `password_hash` | `str` | `""` | — | PBKDF2 派生的密码哈希 |
| `created_at` | `datetime` | 当前时间 | — | 创建时间 |
| `last_login` | `datetime \| null` | `null` | — | 最后登录时间 |
| `is_current` | `bool` | `false` | — | 是否为当前账号 |

> 账号密码**永不**以明文写入配置文件；`encrypted_password` 与 `password_hash` 的分工见 [安全](security.md)。

## 四、`config` 命令用法

### 1. 查看

```bash
dwrg config show                 # 表格：app.* 全部字段 + 渠道服/账号数量
dwrg config show --format json   # 完整配置的 JSON
dwrg config show --key log_level # 单键
```

`--key` 的取键规则见 [CLI 命令参考](cli-reference.md#1-dwrg-config-show)。

### 2. 设置与重置

```bash
dwrg config set log_level DEBUG
dwrg config set max_concurrent_downloads 8
dwrg config set language en-US

dwrg config unset log_level      # 恢复该键默认值
dwrg config reset --force        # 全部恢复默认
```

可设置的键即 `AppConfig` 的全部字段（`server`、`account`、`auto_update`、`verbose`、`language`、`data_dir`、`cache_dir`、`log_level`、`max_concurrent_downloads`、`download_timeout`）。键支持 `log_level` 或 `app.log_level` 两种写法；值以字符串传入，由 Pydantic 自动完成 `"8" → 8`、`"true" → True` 之类的转换。

### 3. 导入与导出

```bash
dwrg config export ./backup.yaml                 # 默认 YAML
dwrg config export ./backup.json --format json   # JSON
dwrg config import ./backup.yaml                 # 按扩展名解析
```

导入会**覆盖**当前配置；导入后若 `app.server` 指向的渠道服在导入内容中不存在，`status` 会显示「未设置」。

### 4. 原子写入

保存配置时先写入同目录临时文件，再用 `os.replace` 原子替换，避免写入中断导致配置损坏。失败时统一抛出 `ConfigError`：

| 场景 | 错误信息 |
|------|----------|
| 文件存在但无法解析 | `配置文件解析失败`（附带 `path` / `reason`） |
| 顶层不是映射 | `配置文件根节点必须是映射` |
| 内容不符合模型 | `配置文件内容不合法` |
| 写入失败 | `配置文件写入失败` |

## 五、环境变量

| 变量 | 读取位置 | 作用 |
|------|----------|------|
| `DWRG_GAME_PATH` | `launcher.manager` | 显式指定游戏可执行文件路径，优先于平台默认探测 |
| `DWRG_ENCRYPTION_KEY` | `security.crypto` | 直接提供 Fernet 密钥；若不是合法 Fernet 密钥则视为口令并做 PBKDF2 派生 |
| `DWRG_KEY_FILE` | `security.crypto` | 自定义密钥文件路径（默认 `~/.dwrg/keyfile`） |

此外，**启动游戏时**会向游戏子进程注入以下变量（由 dwrg 写入，供游戏或外部工具读取）：

| 变量 | 值 |
|------|----|
| `DWRG_LAUNCHED` | `1` |
| `DWRG_ACCOUNT` | 当前启动使用的账号 ID（存在时） |
| `DWRG_SERVER` | 当前启动使用的渠道服（存在时） |

> `DWRG_*` 其余变量（如语言）当前**没有**实现读取逻辑；语言请通过 `--lang` 或 `config set language` 设置。

## 六、相关文件与目录

| 路径 | 内容 |
|------|------|
| `~/.config/dwrg/config.yaml` | 主配置文件 |
| `~/.dwrg/keyfile` | 加密密钥文件（权限 `0600`） |
| `~/.dwrg/logs/dwrg.log` | 滚动日志（单文件上限 5 MiB，保留 5 份） |
| `~/.dwrg/plugins/` | 插件目录 |
| `~/.dwrg/plugins/plugins.json` | 插件启用状态 |
| `~/.dwrg/game/` | 游戏资源目录（= `data_dir/game`） |
| `~/.dwrg/cache/` | 缓存目录 |
| `~/.dwrg/manifest.json` | 本地资源清单 |
