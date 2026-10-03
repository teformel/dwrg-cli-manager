"""插件系统的单元测试。

所有测试均在 ``tmp_path`` 上构造插件目录与状态文件，不触碰真实 ``~/.dwrg``。
"""

from pathlib import Path

import pytest

from dwrg_manager.exceptions import PluginError, ValidationError
from dwrg_manager.plugins import Plugin, PluginManager, PluginMeta, PluginState

#: 一个最小的合法插件模块模板，``{name}`` 会被替换为插件名。
VALID_PLUGIN = '''\
"""测试用插件模块。"""

from dwrg_manager.plugins import Plugin, PluginContext


class DemoPlugin(Plugin):
    """最小可用的合法插件。"""

    name = "{name}"
    version = "1.2.3"
    description = "演示插件"
    author = "tester"

    def __init__(self, context: PluginContext | None = None) -> None:
        super().__init__(context=context)
        self.enable_calls = 0
        self.disable_calls = 0

    def on_enable(self) -> None:
        self.enable_calls += 1

    def on_disable(self) -> None:
        self.disable_calls += 1
'''

#: 一个存在语法错误的插件模块。
BROKEN_PLUGIN = "def broken(:\n    pass\n"


def _make_manager(tmp_path: Path) -> PluginManager:
    """在临时目录上创建互不干扰的插件管理器。"""
    return PluginManager(tmp_path / "plugins", state_file=tmp_path / "plugins.json")


def _write_file_plugin(plugin_dir: Path, name: str, body: str | None = None) -> Path:
    """以 ``<name>.py`` 单文件布局写入插件。"""
    plugin_dir.mkdir(parents=True, exist_ok=True)
    path = plugin_dir / f"{name}.py"
    path.write_text((body or VALID_PLUGIN).format(name=name), encoding="utf-8")
    return path


def _write_dir_plugin(plugin_dir: Path, name: str, body: str | None = None) -> Path:
    """以 ``<name>/plugin.py`` 目录布局写入插件。"""
    sub_dir = plugin_dir / name
    sub_dir.mkdir(parents=True, exist_ok=True)
    path = sub_dir / "plugin.py"
    path.write_text((body or VALID_PLUGIN).format(name=name), encoding="utf-8")
    return path


def test_discover_returns_empty_for_empty_dir(tmp_path: Path) -> None:
    """空插件目录的发现结果为空列表。"""
    plugin_dir = tmp_path / "plugins"
    plugin_dir.mkdir()
    manager = _make_manager(tmp_path)
    assert manager.discover() == []


def test_discover_returns_empty_for_missing_dir(tmp_path: Path) -> None:
    """插件目录不存在时优雅返回空列表，不抛异常。"""
    manager = _make_manager(tmp_path)
    assert manager.plugin_dir == tmp_path / "plugins"
    assert manager.list_plugins() == []
    assert manager.discover() == []


def test_discover_supports_both_layouts(tmp_path: Path) -> None:
    """同时识别 ``*.py`` 与 ``<name>/plugin.py`` 两种布局。"""
    plugin_dir = tmp_path / "plugins"
    _write_file_plugin(plugin_dir, "single")
    _write_dir_plugin(plugin_dir, "packaged")

    manager = _make_manager(tmp_path)
    names = sorted(meta.name for meta in manager.discover())
    assert names == ["packaged", "single"]

    single = manager.get_plugin("single")
    assert single is not None
    assert Path(single.path).name == "single.py"

    packaged = manager.get_plugin("packaged")
    assert packaged is not None
    assert Path(packaged.path).name == "plugin.py"
    assert Path(packaged.path).parent.name == "packaged"


def test_load_valid_plugin_and_call_on_enable(tmp_path: Path) -> None:
    """加载合法插件后启用会触发插件的 on_enable 回调。"""
    plugin_dir = tmp_path / "plugins"
    _write_file_plugin(plugin_dir, "demo")

    manager = _make_manager(tmp_path)
    instance = manager.load_plugin("demo")
    assert isinstance(instance, Plugin)

    loaded_meta = manager.get_plugin("demo")
    assert loaded_meta is not None
    assert loaded_meta.state is PluginState.LOADED
    assert loaded_meta.entry_point.endswith("DemoPlugin")

    assert manager.enable_plugin("demo") is True
    assert instance.enable_calls == 1

    enabled_meta = manager.get_plugin("demo")
    assert enabled_meta is not None
    assert enabled_meta.state is PluginState.ENABLED
    assert enabled_meta.enabled is True


def test_enable_disable_persist_across_instances(tmp_path: Path) -> None:
    """启用/禁用状态持久化到 state_file，并能被新实例读回。"""
    plugin_dir = tmp_path / "plugins"
    _write_file_plugin(plugin_dir, "demo")
    state_file = tmp_path / "plugins.json"

    manager = PluginManager(plugin_dir, state_file=state_file)
    assert manager.enable_plugin("demo") is True
    assert state_file.is_file()
    assert manager.is_enabled("demo") is True

    reopened = PluginManager(plugin_dir, state_file=state_file)
    assert reopened.is_enabled("demo") is True
    reopened_meta = reopened.get_plugin("demo")
    assert reopened_meta is not None
    assert reopened_meta.enabled is True

    assert reopened.disable_plugin("demo") is True

    final = PluginManager(plugin_dir, state_file=state_file)
    assert final.is_enabled("demo") is False
    final_meta = final.get_plugin("demo")
    assert final_meta is not None
    assert final_meta.enabled is False


def test_broken_plugin_isolated_from_others(tmp_path: Path) -> None:
    """语法错误插件被标记为 ERROR，且不影响其它插件加载。"""
    plugin_dir = tmp_path / "plugins"
    _write_file_plugin(plugin_dir, "good")
    _write_file_plugin(plugin_dir, "broken", body=BROKEN_PLUGIN)

    manager = _make_manager(tmp_path)
    names = sorted(meta.name for meta in manager.discover())
    assert names == ["broken", "good"]

    with pytest.raises(PluginError):
        manager.load_plugin("broken")

    broken_meta = manager.get_plugin("broken")
    assert broken_meta is not None
    assert broken_meta.state is PluginState.ERROR
    assert broken_meta.error

    good_instance = manager.load_plugin("good")
    assert isinstance(good_instance, Plugin)
    good_meta = manager.get_plugin("good")
    assert good_meta is not None
    assert good_meta.state is PluginState.LOADED


def test_get_plugin_unknown_returns_none(tmp_path: Path) -> None:
    """未知插件名返回 None。"""
    manager = _make_manager(tmp_path)
    assert manager.get_plugin("does-not-exist") is None


def test_enable_disable_unknown_returns_false(tmp_path: Path) -> None:
    """启用/禁用未知插件返回 False 且不抛异常。"""
    manager = _make_manager(tmp_path)
    assert manager.enable_plugin("nope") is False
    assert manager.disable_plugin("nope") is False
    assert manager.is_enabled("nope") is False


def test_invalid_plugin_name_raises_validation_error(tmp_path: Path) -> None:
    """非法插件名抛出 ValidationError。"""
    manager = _make_manager(tmp_path)
    with pytest.raises(ValidationError):
        manager.load_plugin("bad name")
    with pytest.raises(ValidationError):
        PluginMeta(name="bad name")


def test_plugin_meta_rejects_bad_version() -> None:
    """版本号不符合 x.y.z 时抛出 ValidationError。"""
    with pytest.raises(ValidationError):
        PluginMeta(name="demo", version="1.0")


def test_reload_rescans_and_reenables(tmp_path: Path) -> None:
    """reload 会重新扫描目录并重新启用此前启用的插件。"""
    plugin_dir = tmp_path / "plugins"
    _write_file_plugin(plugin_dir, "demo")

    manager = _make_manager(tmp_path)
    assert manager.enable_plugin("demo") is True

    _write_file_plugin(plugin_dir, "extra")
    metas = manager.reload()
    assert sorted(meta.name for meta in metas) == ["demo", "extra"]
    assert manager.is_enabled("demo") is True

    demo_meta = manager.get_plugin("demo")
    assert demo_meta is not None
    assert demo_meta.state is PluginState.ENABLED
