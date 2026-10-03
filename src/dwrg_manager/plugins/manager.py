"""插件管理器。

负责插件的发现、加载、启用/禁用与状态持久化。插件通过 ``importlib``
从文件动态加载，单个插件加载失败不会影响其它插件。
"""

import importlib.util
import inspect
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from ..exceptions import PluginError, ValidationError
from ..utils.logger import get_logger
from .base import Plugin, PluginContext
from .models import PluginMeta, PluginState, validate_plugin_name

logger = get_logger(__name__)

#: 目录布局下约定作为入口的文件名。
ENTRY_FILENAME = "plugin.py"

#: 启用状态持久化文件名。
STATE_FILENAME = "plugins.json"


class _DefaultPluginContext:
    """:class:`PluginContext` 的默认实现。

    仅提供空配置读取与写日志两类最小能力。
    """

    def __init__(self, name: str) -> None:
        """初始化上下文。

        Args:
            name: 所属插件名，用于日志前缀。
        """
        self._name = name

    def get_config(self) -> dict[str, Any]:
        """返回插件配置（默认为空字典）。"""
        return {}

    def log(self, level: str, message: str) -> None:
        """按级别写入带插件前缀的日志。

        Args:
            level: 日志级别名。
            message: 日志正文。
        """
        text = f"[plugin:{self._name}] {message}"
        level_lower = level.lower()
        if level_lower == "debug":
            logger.debug(text)
        elif level_lower in ("warn", "warning"):
            logger.warning(text)
        elif level_lower in ("error", "critical"):
            logger.error(text)
        else:
            logger.info(text)


class PluginManager:
    """插件管理器。

    Args:
        plugin_dir: 插件根目录；默认 ``~/.dwrg/plugins``。
        state_file: 启用状态持久化文件；默认 ``<plugin_dir>/plugins.json``。

    Example:
        >>> manager = PluginManager()
        >>> manager.list_plugins()
        []
    """

    def __init__(
        self,
        plugin_dir: str | Path | None = None,
        *,
        state_file: str | Path | None = None,
    ) -> None:
        """初始化插件管理器，并读入已持久化的启用状态。

        Args:
            plugin_dir: 插件根目录，缺省为 ``~/.dwrg/plugins``。
            state_file: 启用状态文件，缺省为 ``<plugin_dir>/plugins.json``。
        """
        self._plugin_dir: Path = (
            Path(plugin_dir).expanduser()
            if plugin_dir is not None
            else Path.home() / ".dwrg" / "plugins"
        )
        self._state_file: Path = (
            Path(state_file).expanduser()
            if state_file is not None
            else self._plugin_dir / STATE_FILENAME
        )
        self._metas: dict[str, PluginMeta] = {}
        self._instances: dict[str, Plugin] = {}
        self._enabled: set[str] = self._load_state()
        self._discovered: bool = False

    # ------------------------------------------------------------------ 属性

    @property
    def plugin_dir(self) -> Path:
        """插件根目录。"""
        return self._plugin_dir

    # -------------------------------------------------------------- 发现与查询

    def discover(self) -> list[PluginMeta]:
        """扫描插件目录，识别 ``*.py`` 与 ``<name>/plugin.py`` 两种布局。

        目录不存在或为空时返回空列表，不抛异常。非法命名的条目会被跳过。

        Returns:
            本次发现的插件元数据列表，按名称升序排列。
        """
        self._metas = {}
        directory = self._plugin_dir
        if not directory.is_dir():
            self._discovered = True
            return []
        for entry in sorted(directory.iterdir(), key=lambda item: item.name):
            if entry.name.startswith((".", "_")):
                continue
            if entry.is_file() and entry.suffix == ".py":
                name, path = entry.stem, entry
            elif entry.is_dir() and (entry / ENTRY_FILENAME).is_file():
                name, path = entry.name, entry / ENTRY_FILENAME
            else:
                continue
            try:
                self._metas[name] = self._build_meta(name, path)
            except ValidationError as exc:
                logger.warning(f"跳过非法插件名 {name!r}: {exc}")
        self._discovered = True
        return list(self._metas.values())

    def list_plugins(self) -> list[PluginMeta]:
        """返回已发现的插件（含 enabled 状态）。

        Returns:
            插件元数据列表；若尚未扫描，会先自动执行一次发现。
        """
        self._ensure_discovered()
        return list(self._metas.values())

    def get_plugin(self, name: str) -> PluginMeta | None:
        """按名称获取插件元数据。

        Args:
            name: 插件名。

        Returns:
            对应的 :class:`PluginMeta`；名字未知时返回 ``None``（不抛异常）。
        """
        self._ensure_discovered()
        return self._metas.get(name)

    # -------------------------------------------------------------- 加载与卸载

    def load_plugin(self, name: str) -> Plugin:
        """动态加载指定插件。

        使用 :func:`importlib.util.spec_from_file_location` 从文件加载模块，
        插件模块内可直接 ``from dwrg_manager.plugins import Plugin``。

        Args:
            name: 待加载的插件名。

        Returns:
            加载成功后的插件实例。

        Raises:
            ValidationError: 插件名不符合命名规范。
            PluginError: 插件未发现、入口文件缺失或加载过程中出错。
        """
        validate_plugin_name(name)
        self._ensure_discovered()
        meta = self._metas.get(name)
        if meta is None:
            raise PluginError(f"插件未发现: {name}")
        path = Path(meta.path)
        if not path.is_file():
            self._fail(meta, f"插件入口文件不存在: {path}")
            raise PluginError(f"插件入口文件不存在: {path}")

        module_name = f"dwrg_manager_plugin_{name}"
        try:
            module = self._import_module(module_name, path)
            plugin_cls = self._find_plugin_class(module, path)
            instance = plugin_cls(context=self._make_context(name))
            instance.on_load()
            self._apply_instance_meta(meta, instance, module_name, plugin_cls)
        except PluginError as exc:
            self._instances.pop(name, None)
            self._fail(meta, str(exc))
            raise
        except Exception as exc:
            self._instances.pop(name, None)
            self._fail(meta, str(exc))
            raise PluginError(f"加载插件 {name} 失败: {exc}") from exc

        self._instances[name] = instance
        logger.info(f"已加载插件: {name} v{meta.version}")
        return instance

    def unload_plugin(self, name: str) -> bool:
        """卸载已加载的插件实例。

        Args:
            name: 插件名。

        Returns:
            卸载成功返回 ``True``；插件未加载或名字未知时返回 ``False``。
        """
        self._ensure_discovered()
        if name not in self._instances:
            return False
        meta = self._metas.get(name)
        if meta is not None and meta.enabled:
            try:
                self._instances[name].on_disable()
            except Exception as exc:
                logger.error(f"卸载插件 {name} 时回调失败: {exc}")
        del self._instances[name]
        if meta is not None:
            meta.state = (
                PluginState.ENABLED if name in self._enabled else PluginState.DISCOVERED
            )
        logger.info(f"已卸载插件: {name}")
        return True

    # -------------------------------------------------------------- 启用与禁用

    def enable_plugin(self, name: str) -> bool:
        """启用插件（必要时先加载）。

        Args:
            name: 插件名。

        Returns:
            启用成功返回 ``True``；名字未知或加载/启用失败返回 ``False``，
            且不抛异常（失败原因记录在该插件的 ``error`` 字段）。
        """
        self._ensure_discovered()
        meta = self._metas.get(name)
        if meta is None:
            return False
        try:
            instance = self._instances.get(name)
            if instance is None:
                instance = self.load_plugin(name)
            instance.on_enable()
        except Exception as exc:
            self._fail(meta, str(exc))
            return False
        self._enabled.add(name)
        self._save_state()
        meta.enabled = True
        meta.state = PluginState.ENABLED
        meta.error = None
        return True

    def disable_plugin(self, name: str) -> bool:
        """禁用插件。

        Args:
            name: 插件名。

        Returns:
            禁用成功返回 ``True``；名字未知时返回 ``False``，且不抛异常。
        """
        self._ensure_discovered()
        meta = self._metas.get(name)
        if meta is None:
            return False
        instance = self._instances.get(name)
        if instance is not None and meta.enabled:
            try:
                instance.on_disable()
            except Exception as exc:
                logger.error(f"禁用插件 {name} 时回调失败: {exc}")
        self._enabled.discard(name)
        self._save_state()
        meta.enabled = False
        meta.state = PluginState.DISABLED
        return True

    def is_enabled(self, name: str) -> bool:
        """判断插件是否处于启用状态。

        Args:
            name: 插件名。

        Returns:
            已启用返回 ``True``，否则返回 ``False``。
        """
        self._ensure_discovered()
        return name in self._enabled

    def reload(self) -> list[PluginMeta]:
        """重新扫描并加载插件目录。

        会先卸载全部已加载实例，再重新发现；此前处于启用状态的插件会被
        重新启用。单个插件加载失败只会将其标记为 ``ERROR``，不影响其它插件。

        Returns:
            重新发现后的插件元数据列表。
        """
        for name in list(self._instances):
            self.unload_plugin(name)
        self._instances.clear()
        self._metas.clear()
        self._discovered = False
        metas = self.discover()
        for meta in metas:
            if meta.name in self._enabled:
                self.enable_plugin(meta.name)
        return metas

    # ---------------------------------------------------------------- 内部实现

    def _ensure_discovered(self) -> None:
        """确保至少完成过一次目录扫描。"""
        if not self._discovered:
            self.discover()

    def _build_meta(self, name: str, path: Path) -> PluginMeta:
        """根据插件名与入口路径构造元数据。"""
        enabled = name in self._enabled
        return PluginMeta(
            name=name,
            path=str(path),
            enabled=enabled,
            state=PluginState.ENABLED if enabled else PluginState.DISCOVERED,
        )

    def _import_module(self, module_name: str, path: Path) -> ModuleType:
        """从文件路径动态导入插件模块。"""
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise PluginError(f"无法为插件创建加载器: {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(module_name, None)
            raise
        return module

    def _find_plugin_class(self, module: ModuleType, path: Path) -> type[Plugin]:
        """在插件模块中查找首个在本模块定义的 :class:`Plugin` 子类。"""
        try:
            members = inspect.getmembers(module, inspect.isclass)
        except Exception as exc:
            raise PluginError(f"检查插件模块失败: {path}: {exc}") from exc
        for _, obj in members:
            if not inspect.isclass(obj):
                continue
            if (
                obj is not Plugin
                and issubclass(obj, Plugin)
                and getattr(obj, "__module__", None) == module.__name__
            ):
                return obj
        raise PluginError(f"插件 {path} 中未找到 Plugin 子类")

    def _make_context(self, name: str) -> PluginContext:
        """构造插件运行时上下文。"""
        return _DefaultPluginContext(name)

    def _apply_instance_meta(
        self,
        meta: PluginMeta,
        instance: Plugin,
        module_name: str,
        plugin_cls: type[Plugin],
    ) -> None:
        """用加载到的实例信息补全元数据。"""
        meta.entry_point = f"{module_name}:{plugin_cls.__name__}"
        if instance.version:
            meta.version = instance.version
        if instance.description:
            meta.description = instance.description
        if instance.author:
            meta.author = instance.author
        meta.error = None
        meta.enabled = meta.name in self._enabled
        meta.state = PluginState.ENABLED if meta.enabled else PluginState.LOADED

    def _fail(self, meta: PluginMeta, message: str) -> None:
        """把插件标记为 ``ERROR`` 并记录日志。"""
        meta.state = PluginState.ERROR
        meta.error = message
        logger.error(f"插件 {meta.name} 处理失败: {message}")

    def _load_state(self) -> set[str]:
        """从状态文件读取已启用插件集合；读取失败时返回空集合。"""
        path = self._state_file
        if not path.is_file():
            return set()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(f"读取插件状态文件失败: {exc}")
            return set()
        if not isinstance(raw, dict):
            return set()
        enabled = raw.get("enabled", [])
        if not isinstance(enabled, list):
            return set()
        return {str(item) for item in enabled}

    def _save_state(self) -> None:
        """把已启用插件集合写入状态文件。

        Raises:
            PluginError: 状态文件写入失败。
        """
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(
                {"enabled": sorted(self._enabled)}, ensure_ascii=False, indent=2
            )
            self._state_file.write_text(payload, encoding="utf-8")
        except OSError as exc:
            raise PluginError(f"写入插件状态文件失败: {exc}") from exc
