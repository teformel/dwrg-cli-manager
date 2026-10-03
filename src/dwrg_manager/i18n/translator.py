"""文案翻译核心实现。

本模块提供 :class:`Translator` 以及一组进程级便捷函数，负责按语言加载扁平的
点号键目录（``locales/<lang>.json``），并完成查找、回退与占位符格式化。

目录文件使用「扁平点号键」的 JSON，例如::

    {
        "cli.app.help": "第五人格游戏多渠道服和多账号管理工具",
        "cli.account.add.success": "账号添加成功: {username}"
    }

语言查找回退链为：精确语言 → 同语系基础语言 → ``zh-CN`` 目录 → 调用方传入的
``default`` → 键名本身，任何一步缺失都不会抛异常，保证 UI 至少能显示键名。
"""

import json
from pathlib import Path
from typing import Any

from ..config.models import SUPPORTED_LANGUAGES
from ..exceptions import ValidationError
from ..utils.logger import get_logger

logger = get_logger(__name__)

#: 默认语言，同时作为最终回退语言。
DEFAULT_LANGUAGE = "zh-CN"

#: 「同语系基础语言」阶段需要特殊映射的区域语言。
_REGION_FALLBACKS: dict[str, str] = {"zh-TW": "zh-CN"}

__all__ = [
    "DEFAULT_LANGUAGE",
    "Translator",
    "get_translator",
    "set_language",
    "t",
]


def _base_language(language: str) -> str | None:
    """计算语言在同语系回退阶段的基础形态。

    Args:
        language: 形如 ``en-US`` / ``zh-TW`` 的语言代码。

    Returns:
        基础语言代码；若不存在更基础的形态则返回 ``None``。
        ``zh-TW`` 特判为 ``zh-CN``（繁体回退到简体目录）。
    """
    if language in _REGION_FALLBACKS:
        return _REGION_FALLBACKS[language]
    if "-" in language:
        base = language.split("-", 1)[0]
        return base or None
    return None


class Translator:
    """多语言文案翻译器。

    目录文件按需惰性加载并缓存，缺失或损坏的目录会优雅降级为空字典。

    Args:
        language: 初始语言，必须是 :data:`~dwrg_manager.config.models
            .SUPPORTED_LANGUAGES` 之一。
        catalog_dir: 目录文件所在目录；为 ``None`` 时使用本包下的 ``locales/``。

    Raises:
        ValidationError: ``language`` 不在受支持语言列表内。

    Example:
        >>> translator = Translator("zh-CN")
        >>> translator.t("cli.app.help")
        '第五人格游戏多渠道服和多账号管理工具'
    """

    def __init__(
        self, language: str = DEFAULT_LANGUAGE, catalog_dir: Path | None = None
    ) -> None:
        self._catalog_dir: Path = (
            Path(catalog_dir)
            if catalog_dir is not None
            else Path(__file__).parent / "locales"
        )
        self._catalogs: dict[str, dict[str, str]] = {}
        self._language: str = DEFAULT_LANGUAGE
        self.set_language(language)

    @property
    def language(self) -> str:
        """当前语言。

        Returns:
            当前生效的语言代码。
        """
        return self._language

    @property
    def catalog_dir(self) -> Path:
        """目录文件所在目录。

        Returns:
            语言目录的绝对或相对路径。
        """
        return self._catalog_dir

    @property
    def available_languages(self) -> tuple[str, ...]:
        """本翻译器可切换的语言集合。

        Returns:
            来源于 :data:`~dwrg_manager.config.models.SUPPORTED_LANGUAGES` 的
            全部语言代码。未被翻译的语言会沿回退链返回 ``zh-CN`` 文案。
        """
        return SUPPORTED_LANGUAGES

    def set_language(self, language: str) -> None:
        """切换当前语言。

        Args:
            language: 目标语言代码。

        Raises:
            ValidationError: ``language`` 不在受支持语言列表内。
        """
        if language not in SUPPORTED_LANGUAGES:
            raise ValidationError(f"不支持的语言: {language}")
        self._language = language

    def load_catalog(self, language: str) -> dict[str, str]:
        """加载并缓存指定语言的目录。

        Args:
            language: 语言代码，也允许传入基础语言（如 ``en``）。

        Returns:
            扁平点号键到文案的映射；目录缺失或损坏时返回空字典。
        """
        cached = self._catalogs.get(language)
        if cached is not None:
            return cached
        catalog = self._read_catalog_file(language)
        self._catalogs[language] = catalog
        return catalog

    def _read_catalog_file(self, language: str) -> dict[str, str]:
        """从磁盘读取单个目录文件，任何异常都降级为空字典。

        Args:
            language: 语言代码。

        Returns:
            解析得到的文案映射；失败时为空字典。
        """
        if not language or not all(ch.isalnum() or ch in "-_" for ch in language):
            logger.warning("非法的目录语言标识: %r", language)
            return {}
        path = self._catalog_dir / f"{language}.json"
        try:
            raw_text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.debug("语言目录不存在，使用回退: %s", path)
            return {}
        except OSError as exc:
            logger.warning("读取语言目录失败 %s: %s", path, exc)
            return {}
        try:
            data: Any = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.warning("解析语言目录失败 %s: %s", path, exc)
            return {}
        if not isinstance(data, dict):
            logger.warning("语言目录顶层应为对象: %s", path)
            return {}
        catalog: dict[str, str] = {}
        for key, value in data.items():
            if isinstance(key, str) and isinstance(value, str):
                catalog[key] = value
            else:
                logger.warning("忽略非字符串条目 %s: %r", path, key)
        return catalog

    def _fallback_chain(self) -> tuple[str, ...]:
        """计算当前语言的查找回退链（去重且保序）。

        Returns:
            依次包含精确语言、基础语言与默认语言的元组。
        """
        chain: list[str] = []
        for candidate in (
            self._language,
            _base_language(self._language),
            DEFAULT_LANGUAGE,
        ):
            if candidate and candidate not in chain:
                chain.append(candidate)
        return tuple(chain)

    def _lookup(self, key: str) -> str | None:
        """沿回退链查找键。

        Args:
            key: 扁平点号键。

        Returns:
            命中的文案；全部未命中时返回 ``None``。
        """
        for language in self._fallback_chain():
            catalog = self.load_catalog(language)
            if key in catalog:
                return catalog[key]
        return None

    def has(self, key: str) -> bool:
        """判断键是否可在目录（含回退链）中解析到。

        Args:
            key: 扁平点号键。

        Returns:
            ``True`` 表示能解析到文案（不含 ``default`` / 键名兜底）。
        """
        return self._lookup(key) is not None

    def t(self, key: str, default: str | None = None, **kwargs: Any) -> str:
        """翻译并格式化一条文案。

        Args:
            key: 扁平点号键。
            default: 目录未命中时使用的兜底文案；``None`` 时回退为键名。
            **kwargs: 传给 :meth:`str.format` 的占位符参数。

        Returns:
            格式化后的文案。格式化失败（缺参数等）时降级返回未格式化的原文，
            不会抛异常。

        Example:
            >>> Translator().t("cli.account.add.success", username="abc")
            '账号添加成功: abc'
        """
        template = self._lookup(key)
        if template is None:
            template = default if default is not None else key
        if not kwargs:
            return template
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            logger.debug("占位符格式化失败，返回原文 %s: %s", key, exc)
            return template


#: 进程级单例。
_translator: Translator | None = None


def get_translator() -> Translator:
    """获取进程内共享的翻译器单例。

    Returns:
        进程级 :class:`Translator` 实例（懒加载创建）。
    """
    global _translator
    if _translator is None:
        _translator = Translator()
    return _translator


def set_language(language: str) -> None:
    """切换全局单例的语言。

    Args:
        language: 目标语言代码。

    Raises:
        ValidationError: ``language`` 不在受支持语言列表内。
    """
    get_translator().set_language(language)


def t(key: str, default: str | None = None, **kwargs: Any) -> str:
    """使用全局单例翻译一条文案。

    Args:
        key: 扁平点号键。
        default: 目录未命中时的兜底文案。
        **kwargs: 占位符参数。

    Returns:
        翻译（并格式化）后的文案。
    """
    return get_translator().t(key, default, **kwargs)
