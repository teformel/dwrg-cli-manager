# 插件系统

插件系统允许在不修改主程序的前提下扩展功能。实现位于 `dwrg_manager.plugins`。

## 一、插件目录结构

默认插件根目录为 `~/.dwrg/plugins`，可通过 `dwrg plugin ... --plugin-dir <路径>` 或 `PluginManager(plugin_dir=...)` 覆盖。

扫描支持两种布局：

### 1. 目录布局（推荐）

```text
~/.dwrg/plugins/
├── plugins.json            # 启用状态（由管理器维护）
└── my_plugin/
    └── plugin.py           # 入口文件，固定名 plugin.py
```

### 2. 单文件布局

```text
~/.dwrg/plugins/
└── my_plugin.py            # 文件名（去扩展名）即插件名
```

规则：

- 以 `.` 或 `_` 开头的条目会被跳过；
- 目录布局下必须存在 `plugin.py`（常量 `ENTRY_FILENAME`），否则忽略；
- 插件名由**文件 / 目录名**推导，并需通过命名规范校验。

### 启用状态文件

`plugins.json` 记录已启用的插件集合：

```json
{
  "enabled": ["my-plugin"]
}
```

文件缺失或损坏时按「无启用插件」处理。`--plugin-dir` 未指定时，状态文件位于 `<plugin_dir>/plugins.json`。

## 二、插件基类 `Plugin`

基类定义于 `plugins/base.py`，对外从 `dwrg_manager.plugins` 导出为 `Plugin`。

### 1. 类属性

| 属性 | 默认 | 说明 |
|------|------|------|
| `name` | `""` | 插件唯一名，须满足 `[A-Za-z0-9_-]+` |
| `version` | `0.1.0` | 插件版本，须符合 `x.y.z` |
| `description` | `""` | 插件简介 |
| `author` | `""` | 插件作者 |

### 2. 生命周期方法

| 方法 | 是否必须实现 | 调用时机 |
|------|--------------|----------|
| `__init__(context=None)` | 否 | 实例化时注入运行时上下文 |
| `on_load()` | 否（默认空实现） | 模块成功加载、实例化后立即调用 |
| `on_enable()` | **是（抽象方法）** | 插件被启用时调用 |
| `on_disable()` | 否（默认空实现） | 插件被禁用时调用 |
| `info()` | 否 | 返回根据类属性构造的 `PluginMeta`，`state` 为 `LOADED` |

### 3. 运行时上下文 `PluginContext`

上下文以最小接口暴露能力，避免插件反向依赖管理器内部实现：

| 方法 | 说明 |
|------|------|
| `get_config() -> dict` | 获取当前插件配置字典（默认实现返回空字典） |
| `log(level, message)` | 按级别写日志（默认实现加 `[plugin:<name>]` 前缀） |

## 三、插件元数据 `PluginMeta`

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `name` | `str` | —（必填） | 插件唯一名，`[A-Za-z0-9_-]+` |
| `version` | `str` | `0.1.0` | 版本号，须符合 `x.y.z` |
| `description` | `str` | `""` | 简介 |
| `author` | `str` | `""` | 作者 |
| `enabled` | `bool` | `false` | 是否已启用 |
| `state` | `PluginState` | `discovered` | 当前状态 |
| `path` | `str` | `""` | 插件目录或 `.py` 路径 |
| `entry_point` | `str` | `""` | 形如 `"<module>:<Class>"` |
| `error` | `str \| null` | `null` | 失败原因 |

### 插件状态 `PluginState`

```text
discovered → loaded → enabled ⇄ disabled
                   ↘ error
```

| 取值 | 含义 |
|------|------|
| `discovered` | 已扫描发现，尚未加载 |
| `loaded` | 已成功加载进内存 |
| `enabled` | 已加载且被启用 |
| `disabled` | 已被显式禁用 |
| `error` | 加载或启用过程中发生错误 |

### 命名与版本校验

| 校验 | 正则 | 失败信息 |
|------|------|----------|
| 插件名 | `^[A-Za-z0-9_-]+$` | `非法插件名: '...'，仅允许字母、数字、下划线与连字符` |
| 版本号 | `^\d+\.\d+\.\d+$` | `非法版本号: '...'，需符合 x.y.z` |

## 四、开发示例

### 1. 目录布局插件

```text
~/.dwrg/plugins/greeter/plugin.py
```

```python
"""示例插件：启用时打印一条问候。"""

from dwrg_manager.plugins import Plugin


class GreeterPlugin(Plugin):
    name = "greeter"
    version = "1.0.0"
    description = "启动时打印问候语"
    author = "you"

    def on_load(self) -> None:
        if self.context is not None:
            self.context.log("debug", "greeter 已加载")

    def on_enable(self) -> None:
        if self.context is not None:
            config = self.context.get_config()
            who = config.get("who", "world")
            self.context.log("info", f"hello, {who}")

    def on_disable(self) -> None:
        if self.context is not None:
            self.context.log("info", "greeter 已禁用")
```

要点：

- 插件模块内可直接 `from dwrg_manager.plugins import Plugin`；
- 一个入口文件中**首个在本模块定义**的 `Plugin` 子类会被采用（按类名字母序查找）；
- 插件在管理器中的名称来自**文件 / 目录名**；类属性 `name` 建议与之一致，但元数据名称始终以文件 / 目录名为准（加载时只用实例补全 `version` / `description` / `author`）。

### 2. 单文件插件

```text
~/.dwrg/plugins/simple.py
```

```python
from dwrg_manager.plugins import Plugin


class SimplePlugin(Plugin):
    name = "simple"
    version = "0.1.0"

    def on_enable(self) -> None:
        pass
```

### 3. 加载机制说明

- 使用 `importlib.util.spec_from_file_location` 从文件动态加载；
- 模块以 `dwrg_manager_plugin_<name>` 注册到 `sys.modules`；
- 若入口文件内找不到 `Plugin` 子类，抛出 `插件错误: 插件 <path> 中未找到 Plugin 子类`；
- 单个插件加载失败不会影响其它插件。

## 五、启用与禁用

### 1. 命令行

```bash
dwrg plugin list                       # 列出（表格 / --format json）
dwrg plugin info my-plugin             # 详情（JSON）
dwrg plugin enable my-plugin
dwrg plugin disable my-plugin

# 指定自定义插件目录
dwrg plugin list --plugin-dir ./my-plugins
```

### 2. 编程接口

| 方法 | 说明 |
|------|------|
| `discover()` | 扫描目录，返回 `PluginMeta` 列表（按名升序） |
| `list_plugins()` | 返回已发现插件（必要时自动发现） |
| `get_plugin(name)` | 按名取元数据，未知返回 `None` |
| `load_plugin(name)` | 动态加载，返回 `Plugin` 实例 |
| `unload_plugin(name)` | 卸载实例（若已启用则先调用 `on_disable`） |
| `enable_plugin(name)` | 启用（必要时先加载），成功返回 `True` |
| `disable_plugin(name)` | 禁用，成功返回 `True` |
| `is_enabled(name)` | 是否启用 |
| `reload()` | 重新扫描并加载，此前启用的插件会被重新启用 |

### 3. 失败行为

| 场景 | 行为 |
|------|------|
| 插件名未知 | `enable` / `disable` 返回 `False`，不抛异常 |
| 加载 / 启用出错 | 元数据标记为 `ERROR` 并写入 `error`，`enable_plugin` 返回 `False` |
| 状态文件写入失败 | 抛出 `PluginError` |
| 非法插件名 | 扫描时跳过并记录警告；显式加载时抛出 `ValidationError` |

> 插件是与主程序**同权限**的受信任本地代码，本项目不提供沙箱隔离，请只运行可信插件。
