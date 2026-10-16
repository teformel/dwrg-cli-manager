# CLI 命令参考

本文按 `src/dwrg_manager/cli.py` 的真实实现逐条列出 `dwrg` 的命令、选项与参数。命令名、选项名、短选项与帮助文案均与源码逐字一致。

## 一、通用约定

### 1. 语法记号

| 记号 | 含义 |
|------|------|
| `dwrg` | 命令名 |
| `[OPTIONS]` | 可选选项 |
| `ARGS...` | 位置参数 |
| `TEXT` | 字符串取值 |
| `[--x/-x]` | 同时提供长、短两种写法 |
| `...` | 该参数必需 |

### 2. 全局选项

全局选项必须写在子命令**之前**：

```text
dwrg [OPTIONS] COMMAND [ARGS]...
```

| 选项 | 短写 | 类型 | 默认 | 说明 |
|------|------|------|------|------|
| `--version` | `-V` | 布尔 | `False` | 显示版本信息后立即退出 |
| `--verbose` | `-v` | 布尔 | `False` | 详细输出：日志级别切到 `DEBUG` 并同时输出到终端 |
| `--lang` | — | `TEXT` | `None` | 覆盖配置中的输出语言，例如 `zh-CN` / `en-US` |
| `--help` | — | 布尔 | — | 由 Typer 提供，显示帮助 |

示例：

```bash
dwrg --version
```

```text
DWRG CLI Manager 1.0.0
```

```bash
dwrg --lang en-US server current
```

### 3. 输出约定

| 前缀 | 来源 | 含义 |
|------|------|------|
| `✓` | `_ok()` | 操作成功 |
| `!` | `_warn()` | 警告 / 提示（命令通常仍返回退出码 0） |
| `✗` | `_fail()` / `_cli_errors()` | 失败 |

业务异常（`DWRGError` 及其子类）会被统一转换为单行提示，格式为：

```text
✗ <动作><失败>: <用户可读信息>
```

例如：

```text
✗ 账号添加失败: 参数错误: username: 长度必须在 3-20 个字符之间
```

### 4. 退出码

| 退出码 | 触发场景 |
|--------|----------|
| `0` | 命令成功；`--version`；或在确认提示中回答「否」（`typer.Exit(0)`） |
| `1` | 业务异常（`DWRGError` 子类）经 `_cli_errors` 转换；或 `_fail()` 默认退出码 |
| `2` | 命令行解析错误（缺必填参数、未知命令 / 选项等，由 Typer/Click 产生） |
| `130` | 用户中断（`Ctrl+C`，打印「已取消」） |

> 所有子命令组均设置 `no_args_is_help=True`：直接执行 `dwrg account` 会打印该组帮助而非报错。`launch` 例外，见下文。

## 二、顶层命令

### 1. `dwrg help`

显示命令总览面板。

**语法**

```text
dwrg help
```

无选项、无参数。

**示例**

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

### 2. `dwrg diagnose`

系统诊断：采集系统信息、配置信息、渠道服 / 账号数量与启动条件。

**语法**

```text
dwrg diagnose [OPTIONS]
```

| 选项 | 短写 | 类型 | 默认 | 说明 |
|------|------|------|------|------|
| `--output` | `-o` | `TEXT` | `None` | 把诊断结果以 JSON 写入文件；给出该选项时不再打印表格 |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg diagnose
```

```text
 检查项                    结果
 system.platform           Linux-...
 system.system             Linux
 ...
 launch.game_exists        False
 launch.game_path          None
 launch.disk_space         True
! 未找到游戏客户端，请通过 DWRG_GAME_PATH 环境变量或配置指定路径
```

```bash
dwrg diagnose --output /tmp/dwrg-report.json
```

```text
✓ 诊断报告已写入 /tmp/dwrg-report.json
```

**说明**：表格仅列出 `system.*` 与 `launch.*` 字段（`launch` 的 `recommendations` 除外），`recommendations` 会以警告形式逐条打印。

### 3. `dwrg status`

显示当前渠道服、账号与游戏运行状态。

**语法**

```text
dwrg status [OPTIONS]
```

| 选项 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--config` | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg status
```

```text
 项目          值
 版本          1.0.0
 配置文件      /home/<user>/.config/dwrg/config.yaml
 当前渠道服    official (1.0.0)
 当前账号      未设置
 渠道服数量    3
 账号数量      0
! 游戏未运行
```

> `status` 中的游戏状态取自 `LauncherManager` 的**会话内**进程引用，因此新开进程执行时通常显示「游戏未运行」。

## 三、账号管理 `dwrg account`

### 1. `dwrg account add`

添加账号。

**语法**

```text
dwrg account add [OPTIONS]
```

| 选项 | 短写 | 类型 | 默认 | 必需 | 说明 |
|------|------|------|------|------|------|
| `--username` | `-u` | `TEXT` | — | 是 | 用户名（3–20 位，字母 / 数字 / 下划线） |
| `--password` | `-p` | `TEXT` | — | 是 | 密码；以隐藏输入方式提示录入 |
| `--server` | `-s` | `TEXT` | `official` | 否 | 渠道服名称，必须已存在 |
| `--config` | — | `TEXT` | `None` | 否 | 自定义配置文件路径 |

**示例**

```bash
dwrg account add --username tester --server official
```

```text
Password:
✓ 账号添加成功: tester (3f1c2ab9...)
```

**失败示例**

```text
✗ 账号添加失败: 账号错误: 用户名已存在: tester
```

### 2. `dwrg account list`

列出账号。

**语法**

```text
dwrg account list [OPTIONS]
```

| 选项 | 短写 | 类型 | 默认 | 说明 |
|------|------|------|------|------|
| `--server` | `-s` | `TEXT` | `None` | 仅显示该渠道服下的账号 |
| `--format` | `-f` | `TEXT` | `table` | 输出格式：`table` \| `json` |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg account list
```

```text
 账号ID       用户名   渠道服     当前   最后登录
 3f1c2ab9...  tester   official   ★     2026-10-03 19:45
```

无账号时输出警告 `! 暂无账号`。

`--format json` 会输出账号对象的 JSON 数组（字段与账号模型一致）。

### 3. `dwrg account switch`

切换当前账号。

**语法**

```text
dwrg account switch [OPTIONS] ACCOUNT_ID
```

| 参数 / 选项 | 类型 | 默认 | 说明 |
|-------------|------|------|------|
| `ACCOUNT_ID` | `TEXT` | — | 账号 ID（必需） |
| `--config` | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg account switch 3f1c2ab9-...
```

```text
✓ 账号切换成功
```

```text
✗ 账号不存在: 00000000
```

### 4. `dwrg account remove`

删除账号。

**语法**

```text
dwrg account remove [OPTIONS] ACCOUNT_ID
```

| 参数 / 选项 | 短写 | 类型 | 默认 | 说明 |
|-------------|------|------|------|------|
| `ACCOUNT_ID` | — | `TEXT` | — | 账号 ID（必需） |
| `--force` | `-f` | 布尔 | `False` | 跳过确认 |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg account remove 3f1c2ab9-... --force
```

```text
✓ 账号删除成功
```

不加 `--force` 时会提示 `确定要删除账号 <id> 吗？`；回答「否」时直接退出（退出码 0）。

### 5. `dwrg account status`

查看账号状态。

**语法**

```text
dwrg account status [OPTIONS] [ACCOUNT_ID]
```

| 参数 / 选项 | 类型 | 默认 | 说明 |
|-------------|------|------|------|
| `ACCOUNT_ID` | `TEXT` | `None` | 账号 ID；省略时显示当前账号 |
| `--config` | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg account status
```

```text
账号状态
 账号ID: 3f1c2ab9-...
 用户名: tester
 渠道服: official
 当前账号: 是
 最后登录: 2026-10-03 19:45:30
```

未找到账号时输出 `✗ 未找到账号`。

### 6. `dwrg account login`

登录账号（写入登录态供启动器使用）。

**语法**

```text
dwrg account login [OPTIONS] ACCOUNT_ID
```

| 参数 / 选项 | 短写 | 类型 | 默认 | 说明 |
|-------------|------|------|------|------|
| `ACCOUNT_ID` | — | `TEXT` | — | 账号 ID（必需） |
| `--server` | `-s` | `TEXT` | `None` | 目标渠道服；省略时沿用账号自身配置 |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg account login 3f1c2ab9-... --server official
```

```text
✓ tester 登录 official 成功
```

### 7. `dwrg account logout`

登出当前账号。

**语法**

```text
dwrg account logout [OPTIONS]
```

| 选项 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--config` | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg account logout
```

```text
✓ 已登出账号: tester
```

当前无登录账号时输出 `! 当前没有登录的账号`。

### 8. `dwrg account export`

加密导出全部账号为单个文件。

**语法**

```text
dwrg account export [OPTIONS] PATH
```

| 参数 / 选项 | 类型 | 默认 | 说明 |
|-------------|------|------|------|
| `PATH` | `TEXT` | — | 导出目标文件路径（必需） |
| `--config` | `TEXT` | `None` | 自定义配置文件路径 |

导出文件为 JSON 外壳 + Fernet 加密载荷（含密文密码与哈希），采用原子写入。
没有可导出账号时命令失败。

**示例**

```bash
dwrg account export ~/backup/idv-accounts.json
```

```text
✓ 已导出 2 个账号到 C:\Users\me\backup\idv-accounts.json
```

### 9. `dwrg account import`

从加密导出文件导入并合并账号。

**语法**

```text
dwrg account import [OPTIONS] PATH
```

| 参数 / 选项 | 短写 | 类型 | 默认 | 说明 |
|-------------|------|------|------|------|
| `PATH` | — | `TEXT` | — | 导入的导出文件路径（必需） |
| `--force` | `-f` | 布尔 | `False` | 覆盖已存在的同 ID 账号；省略时跳过 |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

导入采用两段式：先全量校验整个文件（结枌与加密载荷），再逐条应用；
任何一条校验失败都不会写入任何账号。

**示例**

```bash
dwrg account import ~/backup/idv-accounts.json --force
```

```text
  跳过已存在的账号: tester
  新增账号: player2
✓ 导入完成：新增 1，覆盖 0，跳过 1
```

## 四、渠道服管理 `dwrg server`

### 1. `dwrg server list`

列出渠道服。

**语法**

```text
dwrg server list [OPTIONS]
```

| 选项 | 短写 | 类型 | 默认 | 说明 |
|------|------|------|------|------|
| `--format` | `-f` | `TEXT` | `table` | 输出格式：`table` \| `json` |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg server list
```

```text
 名称          状态     版本    地区   默认   地址
 bserver       active   1.0.0   CN            https://game.bilibili.com/idv
 official      active   1.0.0   CN     ★      https://idv.163.com
 test_server   active   1.0.0   CN            https://test.idv.163.com
```

无渠道服时输出 `! 暂无渠道服`。

### 2. `dwrg server current`

显示当前渠道服。

**语法**

```text
dwrg server current [OPTIONS]
```

| 选项 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--config` | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg server current
```

```text
当前渠道服: official (1.0.0)
```

未设置时输出 `! 未设置当前渠道服`。

### 3. `dwrg server detect`

并发探测各渠道服延迟并推荐最优。

**语法**

```text
dwrg server detect [OPTIONS]
```

| 选项 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--config` | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg server detect
```

```text
 名称          状态     延迟(ms)   在线玩家
 bserver       active   42.1       0
 official      active   18.7       0
 test_server   offline  超时       0
✓ 推荐渠道服: official
```

无可用渠道服时输出 `! 未能探测到可用渠道服（离线环境下属正常）`。

### 4. `dwrg server switch`

切换当前渠道服。

**语法**

```text
dwrg server switch [OPTIONS] SERVER_NAME
```

| 参数 / 选项 | 短写 | 类型 | 默认 | 说明 |
|-------------|------|------|------|------|
| `SERVER_NAME` | — | `TEXT` | — | 渠道服名称（必需） |
| `--force` | `-f` | 布尔 | `False` | 跳过确认 |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg server switch bserver --force
```

```text
✓ 已切换到 bserver
```

```text
✗ 渠道服不存在: nope
```

### 5. `dwrg server show`

显示渠道服详情。

**语法**

```text
dwrg server show [OPTIONS] SERVER_NAME
```

| 参数 / 选项 | 类型 | 默认 | 说明 |
|-------------|------|------|------|
| `SERVER_NAME` | `TEXT` | — | 渠道服名称（必需） |
| `--config` | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg server show official
```

```text
渠道服信息 - official
 名称: official
 状态: active
 版本: 1.0.0
 地区: CN
 地址: https://idv.163.com
 延迟: 未知
 最近探测: 尚未探测
```

### 6. `dwrg server info`

`server show` 的**别名**，语法与选项完全一致。

```text
dwrg server info official
```

### 7. `dwrg server add`

新增渠道服。

**语法**

```text
dwrg server add [OPTIONS] NAME
```

| 参数 / 选项 | 短写 | 类型 | 默认 | 说明 |
|-------------|------|------|------|------|
| `NAME` | — | `TEXT` | — | 渠道服名称（必需，`[A-Za-z0-9_-]+`） |
| `--endpoint` | `-e` | `TEXT` | `""` | 接口地址 |
| `--region` | `-r` | `TEXT` | `CN` | 地区 |
| `--version` | — | `TEXT` | `1.0.0` | 版本号 |
| `--default` | — | 布尔 | `False` | 设为默认渠道服 |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg server add myserver --endpoint https://example.com --region CN --default
```

```text
✓ 渠道服已添加: myserver
```

### 8. `dwrg server remove`

删除渠道服。

**语法**

```text
dwrg server remove [OPTIONS] NAME
```

| 参数 / 选项 | 短写 | 类型 | 默认 | 说明 |
|-------------|------|------|------|------|
| `NAME` | — | `TEXT` | — | 渠道服名称（必需） |
| `--force` | `-f` | 布尔 | `False` | 跳过确认 |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg server remove myserver --force
```

```text
✓ 渠道服已删除: myserver
```

### 9. `dwrg server set-default`

设置默认渠道服。

**语法**

```text
dwrg server set-default [OPTIONS] NAME
```

| 参数 / 选项 | 类型 | 默认 | 说明 |
|-------------|------|------|------|
| `NAME` | `TEXT` | — | 渠道服名称（必需） |
| `--config` | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg server set-default bserver
```

```text
✓ 默认渠道服已设置为 bserver
```


## 五、秒级切换 `dwrg checkout` / `dwrg sync` / `dwrg download`

这三个顶层命令对标 `wutheringwaves-cli-manager` 的 `ww checkout` / `ww sync` /
`ww download`，核心是**差异缓存**：首次切换时把当前渠道服的文件快照进
`<游戏目录>/dwrg_server_diff_cache/<渠道服>/`，之后任意切换优先从本地缓存恢复，
不触网、秒级完成；缓存不可用或 `--force-sync` 时才回落下载。

缓存元数据记录在 `<游戏目录>/dwrg_server_diff_cache/<渠道服>/cache_meta.json`，
其中包含 `version` 字段：游戏目录下 `version` 文件内容变化（大版本更新）时会
**自动重置整个差异缓存**，避免把旧版本文件错贴到新版本上。

### 1. `dwrg checkout`

秒级切换渠道服。

**语法**

```text
dwrg checkout [OPTIONS] SERVER
```

| 参数 / 选项 | 短写 | 类型 | 默认 | 说明 |
|-------------|------|------|------|------|
| `SERVER` | — | `TEXT` | — | 目标渠道服名称（必需） |
| `--path` | `-p` | `TEXT` | `None` | 游戏目录；省略时读取配置中的 `game_path`，再回落到 `data_dir/game` |
| `--force-sync` | — | 布尔 | `False` | 跳过缓存，强制走全量下载 |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

**行为**

| 场景 | 结果模式 | 说明 |
|------|----------|------|
| 目标即当前渠道服 | 无需切换 | 只更新快照，不改动任何文件 |
| 两服都有缓存 | 缓存恢复 | 秒级，不触发下载 |
| 只有一服有缓存 | 下载 | 下载缺失文件并回写缓存 |
| 大版本变化 | 下载 | 先自动重置差异缓存，再下载 |

**示例**

```bash
dwrg checkout bserver -p "$HOME/Games/IdentityV"
```

```text
✓ 已切换到 bserver（模式：下载）
  切换前渠道服: official
  下载 2 个文件
```

再次切回即可体验秒级缓存路径：

```bash
dwrg checkout official -p "$HOME/Games/IdentityV"
```

```text
✓ 已切换到 official（模式：缓存恢复）
  切换前渠道服: bserver
  从缓存恢复 2 个文件
```

**失败与保护**

| 情况 | 行为 |
|------|------|
| 目标渠道服不存在 | 抛出 `ServerError`，列出可用渠道服，退出码 1 |
| 已识别渠道服但找不到渠道配置文件 | 直接失败，提示确认游戏目录 |
| 下载失败 | 返回失败结果，**不写缓存**，退出码 1 |
| 缓存路径越界（如 `../`） | 拒绝恢复并回落下载，不会写出游戏目录 |

切换前一定会先备份渠道配置文件（`KRSDKConfig.json` / `*channel*.json` 等，
存放于 `<游戏目录>/dwrg_server_config_backup/`），失败即中止，不会留下
「切了一半」的中间态。

### 2. `dwrg sync`

全量校验本地客户端文件，报告（可选修复）损坏与缺失。

**语法**

```text
dwrg sync [OPTIONS]
```

| 选项 | 短写 | 类型 | 默认 | 说明 |
|------|------|------|------|------|
| `--path` | `-p` | `TEXT` | `None` | 游戏目录；省略时读取配置 |
| `--repair` | — | 布尔 | `False` | 从本地差异缓存修复损坏 / 缺失文件 |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

校验基准是差异缓存中**同渠道服**的快照：缓存里没有对应文件时只校验存在性，
有对应文件时比对 MD5。

**示例**

```bash
dwrg sync -p "$HOME/Games/IdentityV" --repair
```

```text
┌──────────┬────┐
│ 检查项   │ 值 │
├──────────┼────┤
│ 版本     │ 19 │
│ 文件总数 │ 2  │
│ 健康     │ 2  │
│ 损坏     │ 0  │
│ 缺失     │ 0  │
│ 已修复   │ 0  │
└──────────┴────┘
✓ 所有文件校验通过
```

无法识别当前渠道服时命令失败并提示先执行 `dwrg checkout`。

### 3. `dwrg download`

从零下载指定渠道服的客户端框架文件。下载成功后会把文件写回差异缓存、
应用渠道配置并记住游戏目录，使后续 `dwrg checkout` 可以秒级完成。

**语法**

```text
dwrg download [OPTIONS] SERVER
```

| 参数 / 选项 | 短写 | 类型 | 默认 | 说明 |
|-------------|------|------|------|------|
| `SERVER` | — | `TEXT` | — | 目标渠道服名称（必需） |
| `--path` | `-p` | `TEXT` | `None` | 下载目录；省略时读取配置 |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg download official -p "$HOME/Games/IdentityV"
```

```text
✓ 已下载 2 个文件到 C:\Users\me\Games\IdentityV（4096 字节）
```

### 4. 与 `dwrg resource` 的分工

| 命令 | 负责 |
|------|------|
| `dwrg checkout` / `sync` / `download` | 渠道服级别的文件切换、差异缓存与渠道配置管理 |
| `dwrg resource index` / `check` / `update` | 逐文件资源清单（path / size / md5）的生成、校验与增量下载 |

两者共用 `resources.validator` 的哈希实现与 `resources.downloader` 的下载能力，
但不重复实现传输层。

## 六、资源管理 `dwrg resource`

### 0. `dwrg resource index`

扫描本地目录生成资源清单（path / size / md5）。

清单默认写入 `<目录>/manifest.json`（原子写入：临时文件 +
`os.replace`），也可用 `--output` 指定其他路径。

**语法**

```text
dwrg resource index [OPTIONS] DIR
```

| 参数 / 选项 | 类型 | 默认 | 说明 |
|-------------|------|------|------|
| `DIR` | `TEXT` | — | 待扫描的游戏目录（必需） |
| `--output` | `-o` | `TEXT` | `None` | 清单输出路径；缺省为 `<目录>/manifest.json` |
| `--force` | `-f` | 布尔 | `False` | 目标已存在也强制重新生成 |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg resource index "$HOME/Games/IdentityV" -o idv-manifest.json
```

```text
✓ 资源索引已生成: idv-manifest.json（12 个文件，4096000 字节）
```

扫描会跳过 `*.part` / `*.tmp` 与 `manifest.json` 本身，避免把下载中的临时文件
编进清单。

### 1. `dwrg resource check`

检查游戏资源完整性。

**语法**

```text
dwrg resource check [OPTIONS]
```

| 选项 | 短写 | 类型 | 默认 | 说明 |
|------|------|------|------|------|
| `--server` | `-s` | `TEXT` | `None` | 资源服务器名称；省略时使用主用服务器 |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg resource check
```

```text
资源检查结果
 文件总数: 0
 正常文件: 0
 损坏文件: 0
 缺失文件: 0
```

### 2. `dwrg resource verify`

`resource check` 的**别名**，语法与选项完全一致。

### 3. `dwrg resource update`

下载 / 更新游戏资源。

**语法**

```text
dwrg resource update [OPTIONS]
```

| 选项 | 短写 | 类型 | 默认 | 说明 |
|------|------|------|------|------|
| `--server` | `-s` | `TEXT` | `None` | 资源服务器名称 |
| `--force` | `-f` | 布尔 | `False` | 忽略「版本未变」短路，按磁盘现状做修复式更新 |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg resource update
```

```text
✓ 资源更新完成：下载 0 个文件
```

无法获取清单时输出 `✗ 资源更新失败`（错误详情以 `error` 字段携带）。

### 4. `dwrg resource clean`

清理缓存与临时文件。

**语法**

```text
dwrg resource clean [OPTIONS]
```

| 选项 | 短写 | 类型 | 默认 | 说明 |
|------|------|------|------|------|
| `--all` | `-a` | 布尔 | `False` | 清理全部缓存（否则仅删 `.tmp` / `.part` 临时文件） |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg resource clean --all
```

```text
✓ 缓存清理完成
```

### 5. `dwrg resource info`

显示缓存与游戏目录信息。

**语法**

```text
dwrg resource info [OPTIONS]
```

| 选项 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--config` | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg resource info
```

```text
 项目          值
 缓存目录      /home/<user>/.dwrg/cache
 缓存文件数    0
 缓存大小      0.00 B
 游戏目录      /home/<user>/.dwrg/game
 游戏文件数    0
 游戏大小      0.00 B
```

## 七、启动管理 `dwrg launch`

`launch` 是唯一带回调（callback）的命令组：`invoke_without_command=True`，因此**不带子命令**时直接执行启动逻辑。

### 1. `dwrg launch`（等同 `start`）

启动游戏。

**语法**

```text
dwrg launch [OPTIONS]
dwrg launch start [OPTIONS]
```

| 选项 | 短写 | 类型 | 默认 | 说明 |
|------|------|------|------|------|
| `--account` | `-a` | `TEXT` | `None` | 账号 ID；省略时沿用当前账号 |
| `--server` | `-s` | `TEXT` | `None` | 渠道服；省略时沿用当前渠道服 |
| `--verbose` | `-v` | 布尔 | `False` | 透传游戏子进程输出 |
| `--dry-run` | — | 布尔 | `False` | 只打印启动计划（命令行 / 环境变量 / 工作目录），不真正启动 |
| `--graphics` | `-g` | `TEXT` | `None` | 画质档位 `sd` / `hd` / `uhd`；省略时用 `hd`，以 `-graphics=<档位>` 透传 |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg launch --server official
```

```text
✓ 游戏已启动，进程ID: 12345
```

未找到可执行文件时；启动前检查的每一项失败都会附带可执行的修复建议：

```text
✗ 启动前检查未通过: 未找到游戏可执行文件（已尝试 DWRG_GAME_PATH 与默认安装路径）
  （建议: 请设置环境变量 DWRG_GAME_PATH 指向客户端可执行文件，或运行 dwrg diagnose 查看已探测到的安装位置）
```

用 `--dry-run` 只查看将会执行什么：

```bash
dwrg launch --dry-run --graphics uhd
```

```text
工作目录: C:\Users\me\Games\IdentityV
可执行文件: C:\Users\me\Games\IdentityV\IdentityV.exe
渠道服: official
命令行: C:\Users\me\Games\IdentityV\IdentityV.exe -fullscreen -high -thread 4 -graphics=uhd
环境变量: DWRG_LAUNCHED=1, DWRG_SERVER=official
```

### 2. `dwrg launch stop`

停止游戏进程。

**语法**

```text
dwrg launch stop [OPTIONS]
```

| 选项 | 短写 | 类型 | 默认 | 说明 |
|------|------|------|------|------|
| `--force` | `-f` | 布尔 | `False` | 强制终止（否则先尝试优雅终止，超时 10 秒后强杀） |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg launch stop
```

```text
✓ 游戏进程已停止
```

### 3. `dwrg launch status`

显示本次会话中游戏进程的状态。

**语法**

```text
dwrg launch status [OPTIONS]
```

| 选项 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--config` | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg launch status
```

```text
✓ 游戏运行中：PID 12345，CPU 3.2%，内存 512.0 MB，已运行 42s
```

```text
! 游戏未在本会话中运行
```

## 八、配置管理 `dwrg config`

### 1. `dwrg config show`

显示配置。

**语法**

```text
dwrg config show [OPTIONS]
```

| 选项 | 短写 | 类型 | 默认 | 说明 |
|------|------|------|------|------|
| `--key` | `-k` | `TEXT` | `None` | 仅显示指定配置项 |
| `--format` | `-f` | `TEXT` | `table` | 输出格式：`table` \| `json` |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg config show
```

```text
 配置项                        值
 app.server                    official
 app.account                   None
 app.auto_update               True
 app.verbose                   False
 app.language                  zh-CN
 app.data_dir                  ~/.dwrg
 app.cache_dir                 ~/.dwrg/cache
 app.log_level                 INFO
 app.max_concurrent_downloads  5
 app.download_timeout          300
 servers                       3 个渠道服
 accounts                      0 个账号
```

```bash
dwrg config show --key log_level
```

```text
log_level: INFO
```

**关于 `--key` 的取键规则**：实现会先判断键是否为顶层键（`app` / `servers` / `accounts`），否则自动补 `app.` 前缀。因此：

- `--key log_level`、`--key language` 等 **app 子键**可直接书写；
- `--key app`、`--key servers`、`--key accounts` 返回对应**整段**内容；
- 不要写成 `--key app.log_level`（会被拼成 `app.app.log_level` 而报 `✗ 配置项不存在`）。

### 2. `dwrg config set`

设置配置项。

**语法**

```text
dwrg config set [OPTIONS] KEY VALUE
```

| 参数 / 选项 | 类型 | 默认 | 说明 |
|-------------|------|------|------|
| `KEY` | `TEXT` | — | 配置键，例如 `log_level`（也接受 `app.log_level`） |
| `VALUE` | `TEXT` | — | 配置值（字符串形式，由 Pydantic 自动转换类型） |
| `--config` | `TEXT` | `None` | 自定义配置文件路径 |

可设置的键即 `AppConfig` 的全部字段，见 [配置](configuration.md)。

**示例**

```bash
dwrg config set log_level DEBUG
```

```text
✓ 配置已更新: log_level = DEBUG
```

**失败示例**

```text
✗ 设置配置失败: 配置错误: 不支持的配置项: nope，可用: server, account, auto_update, verbose, language, data_dir, cache_dir, log_level, max_concurrent_downloads, download_timeout
```

### 3. `dwrg config unset`

把配置项恢复为默认值。

**语法**

```text
dwrg config unset [OPTIONS] KEY
```

| 参数 / 选项 | 类型 | 默认 | 说明 |
|-------------|------|------|------|
| `KEY` | `TEXT` | — | 配置键 |
| `--config` | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg config unset log_level
```

```text
✓ 配置项已重置: log_level
```

### 4. `dwrg config reset`

重置全部配置为默认值。

**语法**

```text
dwrg config reset [OPTIONS]
```

| 选项 | 短写 | 类型 | 默认 | 说明 |
|------|------|------|------|------|
| `--force` | `-f` | 布尔 | `False` | 跳过确认 |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg config reset --force
```

```text
✓ 配置已重置为默认值
```

不加 `--force` 时会提示 `确定要重置全部配置吗？`。

### 5. `dwrg config export`

导出配置。

**语法**

```text
dwrg config export [OPTIONS] PATH
```

| 参数 / 选项 | 短写 | 类型 | 默认 | 说明 |
|-------------|------|------|------|------|
| `PATH` | — | `TEXT` | — | 导出目标路径（必需） |
| `--format` | `-f` | `TEXT` | `yaml` | 导出格式：`yaml` \| `json` |
| `--config` | — | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg config export backup.json --format json
```

```text
✓ 配置已导出到 <绝对路径>/backup.json
```

### 6. `dwrg config import`

导入配置（覆盖当前配置）。

**语法**

```text
dwrg config import [OPTIONS] PATH
```

| 参数 / 选项 | 类型 | 默认 | 说明 |
|-------------|------|------|------|
| `PATH` | `TEXT` | — | 待导入的配置文件路径（必需） |
| `--config` | `TEXT` | `None` | 自定义配置文件路径 |

**示例**

```bash
dwrg config import backup.json
```

```text
✓ 配置已从 backup.json 导入
```

> 导入格式按**文件扩展名**判断：`.json` 走 JSON，其余走 YAML。

## 九、插件管理 `dwrg plugin`

插件子命令**不支持** `--config`，改用 `--plugin-dir` 指定插件目录（默认 `~/.dwrg/plugins`）。

### 1. `dwrg plugin list`

列出已安装插件。

**语法**

```text
dwrg plugin list [OPTIONS]
```

| 选项 | 短写 | 类型 | 默认 | 说明 |
|------|------|------|------|------|
| `--format` | `-f` | `TEXT` | `table` | 输出格式：`table` \| `json` |
| `--plugin-dir` | — | `TEXT` | `None` | 插件目录 |

**示例**

```bash
dwrg plugin list
```

```text
 名称       版本    状态   描述
 my-plugin  0.1.0   启用   示例插件
```

无插件时输出 `! 未发现插件`。

### 2. `dwrg plugin info`

显示插件详情（以 JSON 输出）。

**语法**

```text
dwrg plugin info [OPTIONS] NAME
```

| 参数 / 选项 | 类型 | 默认 | 说明 |
|-------------|------|------|------|
| `NAME` | `TEXT` | — | 插件名称（必需） |
| `--plugin-dir` | `TEXT` | `None` | 插件目录 |

**示例**

```bash
dwrg plugin info my-plugin
```

```json
{
  "name": "my-plugin",
  "version": "0.1.0",
  "description": "",
  "author": "",
  "enabled": false,
  "state": "discovered",
  "path": "/home/<user>/.dwrg/plugins/my_plugin/plugin.py",
  "entry_point": "",
  "error": null
}
```

> `plugin info` 只读取**发现阶段**的元数据：`version` / `description` / `author` / `entry_point` 会在插件被实际加载后由实例信息补全，因此尚未启用时多为默认值（`0.1.0` / 空串）。字段以 `PluginMeta` 为准，路径因实际安装位置而异。

### 3. `dwrg plugin enable` / `dwrg plugin disable`

启用 / 禁用插件。

**语法**

```text
dwrg plugin enable [OPTIONS] NAME
dwrg plugin disable [OPTIONS] NAME
```

| 参数 / 选项 | 类型 | 默认 | 说明 |
|-------------|------|------|------|
| `NAME` | `TEXT` | — | 插件名称（必需） |
| `--plugin-dir` | `TEXT` | `None` | 插件目录 |

**示例**

```bash
dwrg plugin enable my-plugin
```

```text
✓ 插件已启用: my-plugin
```

```text
✗ 启用失败: my-plugin
```

> `dwrg plugin` 目前仅提供 `list` / `info` / `enable` / `disable`，**没有** `install` / `uninstall` 子命令；插件通过将文件放入插件目录来「安装」。

## 十、抽卡记录 `dwrg gacha`

扫描游戏日志目录，提取抽卡记录链接（对标 `ww log`）。

**语法**

```text
dwrg gacha [OPTIONS]
dwrg gacha scan [OPTIONS]
```

`dwrg gacha` 与 `dwrg gacha scan` 完全等价。

| 选项 | 短写 | 类型 | 默认 | 说明 |
|------|------|------|------|------|
| `--dir` | `-p` | `TEXT` | `None` | 游戏日志目录；缺省按平台自动探测 |
| `--open` | `-o` | 布尔 | `False` | 在默认浏览器中打开第一条链接 |

**平台默认日志目录**

| 平台 | 路径 |
|------|------|
| Windows | `%LOCALAPPDATA%\IdentityV` |
| macOS | `~/Library/Application Support/IdentityV` |
| Linux | `~/.IdentityV` |

**示例**

```bash
dwrg gacha
```

```text
┌──────┬─────────────────────────────────────┐
│ 序号   抽卡记录链接                            │
├──────┼─────────────────────────────────────┤
│ 1      https://gacha.identityv.com/record?id=xxx      │
└──────┴─────────────────────────────────────┘
共 1 条链接，扫描目录 C:\Users\me\AppData\Local\IdentityV（18 个文件）
```

日志被客户端加密时，命令输出提示而不报错：

```text
! 日志已被客户端加密，无法提取抽卡记录链接
```

## 十一、自更新 `dwrg self-update`

检查 PyPI 上的最新版本（对标 `ww update` 的版本检查部分）。

**语法**

```text
dwrg self-update [OPTIONS]
```

| 选项 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `--check` | 布尔 | `False` | 只检查是否有新版本，不执行更新 |
| `--config` | `TEXT` | `None` | 自定义配置文件路径（保留供统一） |

**示例**

```bash
dwrg self-update --check
```

```text
当前版本: 1.0.0
最新版本: 1.1.0
! 发现新版本 1.1.0，可执行 dwrg self-update 升级
```

发现新版本时，命令会打印可直接复制的升级命令：

```text
✓ uv tool install -U dwrg-cli-manager
✓ pip install -U dwrg-cli-manager
```

离线或查询失败时仅输出警告，**不会导致命令失败**（退出码 0）。

