"""``dwrg_manager.i18n`` 单元测试。

覆盖：默认语言、切换语言、回退到 ``default``、键不存在返回键名、占位符格式化、
非法语言抛 :class:`~dwrg_manager.exceptions.ValidationError`、目录缺失优雅降级、
中英文日期时间差异、时长与相对时间本地化。

所有自定义目录都通过 pytest 的 ``tmp_path`` 构造，不触碰真实 ``~/.dwrg``。
"""

import json
from collections.abc import Iterator
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from dwrg_manager.exceptions import ValidationError
from dwrg_manager.i18n import (
    Translator,
    format_date,
    format_datetime,
    format_duration,
    format_relative_time,
    format_time,
    get_translator,
    set_language,
    t,
)

ZH_HELP = "第五人格游戏多渠道服和多账号管理工具"


@pytest.fixture(autouse=True)
def _reset_language() -> Iterator[None]:
    """每个用例前后把全局语言复位为中文，避免用例间相互污染。"""
    set_language("zh-CN")
    yield
    set_language("zh-CN")


# --------------------------------------------------------------------------- #
# 翻译器基础行为
# --------------------------------------------------------------------------- #


def test_default_language_is_chinese() -> None:
    assert Translator().language == "zh-CN"
    assert get_translator().language == "zh-CN"
    assert t("cli.app.help") == ZH_HELP


def test_get_translator_returns_singleton() -> None:
    assert get_translator() is get_translator()


def test_set_language_switches_translation() -> None:
    set_language("en-US")
    assert get_translator().language == "en-US"
    translated = t("cli.app.help")
    assert translated != ZH_HELP
    assert "Identity V" in translated


def test_instance_set_language() -> None:
    translator = Translator()
    translator.set_language("en-US")
    assert translator.language == "en-US"
    assert translator.t("cli.group.account") == "Account Management"


def test_available_languages() -> None:
    languages = Translator().available_languages
    assert isinstance(languages, tuple)
    assert "zh-CN" in languages
    assert "en-US" in languages


def test_invalid_language_raises_validation_error() -> None:
    with pytest.raises(ValidationError):
        Translator().set_language("xx-XX")
    with pytest.raises(ValidationError):
        set_language("not-a-language")
    with pytest.raises(ValidationError):
        Translator(language="klingon")


# --------------------------------------------------------------------------- #
# 回退链
# --------------------------------------------------------------------------- #


def test_fallback_to_default_argument() -> None:
    translator = Translator()
    assert translator.t("does.not.exist", default="兜底文案") == "兜底文案"
    assert t("does.not.exist", default="兜底文案") == "兜底文案"


def test_missing_key_returns_key() -> None:
    translator = Translator()
    assert translator.t("totally.missing.key") == "totally.missing.key"
    assert not translator.has("totally.missing.key")
    assert translator.has("cli.app.help")


def test_base_language_fallback(tmp_path: Path) -> None:
    (tmp_path / "en.json").write_text(
        json.dumps({"greeting": "Hello"}), encoding="utf-8"
    )
    translator = Translator("en-US", catalog_dir=tmp_path)
    assert translator.t("greeting") == "Hello"


def test_zh_tw_falls_back_to_zh_cn(tmp_path: Path) -> None:
    (tmp_path / "zh-CN.json").write_text(json.dumps({"k": "中文"}), encoding="utf-8")
    translator = Translator("zh-TW", catalog_dir=tmp_path)
    assert translator.language == "zh-TW"
    assert translator.t("k") == "中文"


# --------------------------------------------------------------------------- #
# 占位符格式化
# --------------------------------------------------------------------------- #


def test_placeholder_formatting_from_catalog() -> None:
    assert t("cli.account.add.success", username="abc") == "账号添加成功: abc"
    assert t("cli.server.detect.best", name="official") == "推荐渠道服: official"


def test_placeholder_formatting_with_explicit_default() -> None:
    result = t(
        "cli.account.add.success",
        default="账号添加成功: {username}",
        username="abc",
    )
    assert result == "账号添加成功: abc"


def test_missing_placeholder_argument_degrades() -> None:
    assert t("cli.account.add.success") == "账号添加成功: {username}"
    assert t("cli.account.add.success", other="x") == "账号添加成功: {username}"


# --------------------------------------------------------------------------- #
# 目录缺失 / 损坏时的优雅降级
# --------------------------------------------------------------------------- #


def test_missing_catalog_dir_degrades(tmp_path: Path) -> None:
    translator = Translator("zh-CN", catalog_dir=tmp_path)
    assert translator.load_catalog("zh-CN") == {}
    assert translator.t("cli.app.help") == "cli.app.help"
    assert translator.t("cli.app.help", default="默认") == "默认"
    assert not translator.has("cli.app.help")


def test_malformed_catalog_degrades(tmp_path: Path) -> None:
    (tmp_path / "zh-CN.json").write_text("{ not valid json", encoding="utf-8")
    translator = Translator("zh-CN", catalog_dir=tmp_path)
    assert translator.load_catalog("zh-CN") == {}
    assert translator.t("k", default="d") == "d"


def test_non_object_catalog_degrades(tmp_path: Path) -> None:
    (tmp_path / "zh-CN.json").write_text("[1, 2, 3]", encoding="utf-8")
    translator = Translator("zh-CN", catalog_dir=tmp_path)
    assert translator.load_catalog("zh-CN") == {}


def test_load_custom_catalog(tmp_path: Path) -> None:
    (tmp_path / "zh-CN.json").write_text(json.dumps({"a.b": "你好"}), encoding="utf-8")
    translator = Translator("zh-CN", catalog_dir=tmp_path)
    assert translator.load_catalog("zh-CN") == {"a.b": "你好"}
    assert translator.t("a.b") == "你好"
    assert translator.has("a.b")


def test_shipped_catalogs_are_consistent() -> None:
    translator = Translator()
    zh = translator.load_catalog("zh-CN")
    en = translator.load_catalog("en-US")
    assert len(zh) >= 40
    assert len(en) >= 40
    assert set(zh) == set(en)


# --------------------------------------------------------------------------- #
# 日期时间本地化
# --------------------------------------------------------------------------- #


def test_format_datetime_differs_between_languages() -> None:
    value = datetime(2026, 10, 3, 19, 45)
    zh = format_datetime(value, language="zh-CN")
    en = format_datetime(value, language="en-US")
    assert zh != en
    assert zh == "2026年10月03日 19:45"
    assert en == "Oct 3, 2026 7:45 PM"


def test_format_datetime_uses_active_language() -> None:
    value = datetime(2026, 10, 3, 19, 45)
    assert format_datetime(value) == "2026年10月03日 19:45"
    set_language("en-US")
    assert format_datetime(value) == "Oct 3, 2026 7:45 PM"


def test_format_datetime_variants() -> None:
    value = datetime(2026, 10, 3, 19, 45, 30)
    assert format_datetime(value, "short", "zh-CN") == "2026-10-03 19:45"
    assert format_datetime(value, "iso", "zh-CN") == "2026-10-03T19:45:30"
    assert format_datetime(value, "long", "en-US") == "October 3, 2026 7:45:30 PM"
    assert format_datetime(value, "unknown", "zh-CN") == format_datetime(
        value, "medium", "zh-CN"
    )


def test_format_date_and_time() -> None:
    value = datetime(2026, 10, 3, 19, 45, 30)
    assert format_date(value, language="zh-CN") == "2026年10月03日"
    assert format_date(date(2026, 10, 3), language="en-US") == "Oct 3, 2026"
    assert format_time(value, language="zh-CN") == "19:45:30"
    assert format_time(value, language="en-US") == "7:45:30 PM"


# --------------------------------------------------------------------------- #
# 时长与相对时间本地化
# --------------------------------------------------------------------------- #


def test_format_duration_localized() -> None:
    set_language("zh-CN")
    assert format_duration(3723) == "1小时2分3秒"
    assert format_duration(125) == "2分5秒"
    assert format_duration(0) == "0秒"
    set_language("en-US")
    assert format_duration(3723) == "1h 2m 3s"
    assert format_duration(125) == "2m 5s"
    assert format_duration(0) == "0s"


def test_format_relative_time_localized() -> None:
    now = datetime(2026, 10, 3, 19, 45, 0)
    past = now - timedelta(minutes=3)
    future = now + timedelta(minutes=3)
    set_language("zh-CN")
    assert format_relative_time(past, now) == "3分钟前"
    assert format_relative_time(future, now) == "3分钟后"
    set_language("en-US")
    assert format_relative_time(past, now) == "3 minutes ago"
    assert format_relative_time(future, now) == "in 3 minutes"


def test_format_relative_time_boundaries() -> None:
    now = datetime(2026, 10, 3, 19, 45, 0)
    set_language("zh-CN")
    assert format_relative_time(now - timedelta(seconds=3), now) == "刚刚"
    assert format_relative_time(now - timedelta(days=2), now) == "2天前"
    set_language("en-US")
    assert format_relative_time(now - timedelta(seconds=3), now) == "just now"
    assert format_relative_time(now - timedelta(minutes=1), now) == "1 minute ago"
    assert format_relative_time(now - timedelta(hours=5), now) == "5 hours ago"
