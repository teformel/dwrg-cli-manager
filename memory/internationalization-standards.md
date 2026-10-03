---
name: internationalization-standards-dwrg
description: 第五人格命令行管理器的国际化标准和规范
metadata:
  type: project
  created_date: 2026-09-21
      status: active
---

# 国际化标准和规范 - 第五人格命令行管理器

## 国际化理念

基于Vibe Coding理念，我们将国际化作为项目设计的核心要素，确保工具能够服务于全球用户。采用i18n（国际化）和l10n（本地化）最佳实践，支持多语言、多地区、多编码的文本处理。

## 国际化架构

### 1. 国际化层次模型

```
┌─────────────────────────────────────────────────────┐
│                   用户界面层                         │
│  • CLI命令输出  • 错误信息  • 帮助文档  • 提示信息     │
├─────────────────────────────────────────────────────┤
│                   业务逻辑层                         │
│  • 账号管理  • 渠道服管理  • 资源管理  • 配置管理     │
├─────────────────────────────────────────────────────┤
│                   数据存储层                         │
│  • 配置文件  • 日志文件  • 缓存文件  • 用户数据       │
├─────────────────────────────────────────────────────┤
│                   系统层                             │
│  • 文件系统  • 网络协议  • 字符编码  • 时区处理       │
└─────────────────────────────────────────────────────┘
```

### 2. 支持的语言和地区

| 语言 | 语言代码 | 地区 | 国家/地区 | 状态 |
|------|----------|------|-----------|------|
| 简体中文 | zh-CN | 中国大陆 | 主要 | 完全支持 |
| 繁体中文 | zh-TW | 台湾地区 | 主要 | 完全支持 |
| 英语 | en-US | 美国 | 主要 | 完全支持 |
| 日语 | ja-JP | 日本 | 次要 | 完全支持 |
| 韩语 | ko-KR | 韩国 | 次要 | 完全支持 |
| 法语 | fr-FR | 法国 | 次要 | 基础支持 |
| 德语 | de-DE | 德国 | 次要 | 基础支持 |
| 西班牙语 | es-ES | 西班牙 | 次要 | 基础支持 |
| 俄语 | ru-RU | 俄罗斯 | 次要 | 基础支持 |

## 国际化实现规范

### 1. 消息国际化规范

```python
# src/dwrg_manager/i18n/translator.py
import os
import json
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass
from enum import Enum

class Language(Enum):
    """支持的语言"""
    ZH_CN = "zh-CN"    # 简体中文
    ZH_TW = "zh-TW"    # 繁体中文
    EN_US = "en-US"    # 英语
    JA_JP = "ja-JP"    # 日语
    KO_KR = "ko-KR"    # 韩语
    FR_FR = "fr-FR"    # 法语
    DE_DE = "de-DE"    # 德语
    ES_ES = "es-ES"    # 西班牙语
    RU_RU = "ru-RU"    # 俄语

@dataclass
class Locale:
    """语言环境"""
    language: Language
    display_name: str
    native_name: str
    country: str
    currency: str
    date_format: str
    time_format: str
    number_format: str

class Translator:
    """翻译器"""
    
    def __init__(self, locale_dir: Path = None):
        self.locale_dir = locale_dir or Path(__file__).parent / "locales"
        self.current_language = Language.ZH_CN
        self.fallback_language = Language.EN_US
        self.translations: Dict[str, Dict[str, str]] = {}
        self.locales: Dict[Language, Locale] = {}
        
        # 初始化
        self._init_locales()
        self._load_translations()
    
    def _init_locales(self):
        """初始化语言环境"""
        self.locales = {
            Language.ZH_CN: Locale(
                language=Language.ZH_CN,
                display_name="简体中文",
                native_name="简体中文",
                country="中国",
                currency="CNY",
                date_format="%Y-%m-%d",
                time_format="%H:%M:%S",
                number_format=","
            ),
            Language.ZH_TW: Locale(
                language=Language.ZH_TW,
                display_name="繁体中文",
                native_name="繁體中文",
                country="台湾",
                currency="TWD",
                date_format="%Y-%m-%d",
                time_format="%H:%M:%S",
                number_format=","
            ),
            Language.EN_US: Locale(
                language=Language.EN_US,
                display_name="English",
                native_name="English",
                country="United States",
                currency="USD",
                date_format="%Y-%m-%d",
                time_format="%H:%M:%S",
                number_format=","
            ),
            Language.JA_JP: Locale(
                language=Language.JA_JP,
                display_name="日本語",
                native_name="日本語",
                country="日本",
                currency="JPY",
                date_format="%Y/%m/%d",
                time_format="%H:%M:%S",
                number_format=","
            ),
            Language.KO_KR: Locale(
                language=Language.KO_KR,
                display_name="한국어",
                native_name="한국어",
                country="한국",
                currency="KRW",
                date_format="%Y-%m-%d",
                time_format="%H:%M:%S",
                number_format=","
            ),
            Language.FR_FR: Locale(
                language=Language.FR_FR,
                display_name="Français",
                native_name="Français",
                country="France",
                currency="EUR",
                date_format="%d/%m/%Y",
                time_format="%H:%M:%S",
                number_format=","
            ),
            Language.DE_DE: Locale(
                language=Language.DE_DE,
                display_name="Deutsch",
                native_name="Deutsch",
                country="Deutschland",
                currency="EUR",
                date_format="%d.%m.%Y",
                time_format="%H:%M:%S",
                number_format=","
            ),
            Language.ES_ES: Locale(
                language=Language.ES_ES,
                display_name="Español",
                native_name="Español",
                country="España",
                currency="EUR",
                date_format="%d/%m/%Y",
                time_format="%H:%M:%S",
                number_format=","
            ),
            Language.RU_RU: Locale(
                language=Language.RU_RU,
                display_name="Русский",
                native_name="Русский",
                country="Россия",
                currency="RUB",
                date_format="%d.%m.%Y",
                time_format="%H:%M:%S",
                number_format=","
            )
        }
    
    def _load_translations(self):
        """加载翻译文件"""
        for language in Language:
            translation_file = self.locale_dir / f"{language.value}.json"
            if translation_file.exists():
                try:
                    with open(translation_file, 'r', encoding='utf-8') as f:
                        self.translations[language.value] = json.load(f)
                except Exception as e:
                    print(f"Error loading translations for {language.value}: {e}")
            else:
                print(f"Translation file not found: {translation_file}")
    
    def set_language(self, language: Language):
        """设置当前语言"""
        if language in self.locales:
            self.current_language = language
        else:
            print(f"Unsupported language: {language}")
    
    def get_language(self) -> Language:
        """获取当前语言"""
        return self.current_language
    
    def get_locale(self, language: Language = None) -> Locale:
        """获取语言环境"""
        if language is None:
            language = self.current_language
        return self.locales.get(language, self.locales[Language.EN_US])
    
    def translate(self, key: str, **kwargs) -> str:
        """翻译文本"""
        # 尝试当前语言
        if self.current_language.value in self.translations:
            translation = self._get_nested_value(self.translations[self.current_language.value], key)
            if translation:
                return self._format_translation(translation, **kwargs)
        
        # 尝试回退语言
        if self.fallback_language.value in self.translations:
            translation = self._get_nested_value(self.translations[self.fallback_language.value], key)
            if translation:
                return self._format_translation(translation, **kwargs)
        
        # 返回key本身
        return key
    
    def _get_nested_value(self, data: Dict[str, Any], key: str) -> Optional[str]:
        """获取嵌套字典中的值"""
        keys = key.split('.')
        current = data
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None
        
        return current if isinstance(current, str) else None
    
    def _format_translation(self, translation: str, **kwargs) -> str:
        """格式化翻译文本"""
        try:
            return translation.format(**kwargs)
        except KeyError:
            return translation
    
    def get_available_languages(self) -> List[Language]:
        """获取可用语言列表"""
        return list(self.locales.keys())
    
    def get_current_locale_info(self) -> Dict[str, Any]:
        """获取当前语言环境信息"""
        locale = self.get_locale()
        return {
            'language': locale.language.value,
            'display_name': locale.display_name,
            'native_name': locale.native_name,
            'country': locale.country,
            'currency': locale.currency,
            'date_format': locale.date_format,
            'time_format': locale.time_format,
            'number_format': locale.number_format
        }

# 全局翻译器实例
translator = Translator()

def _(key: str, **kwargs) -> str:
    """翻译函数，简化使用"""
    return translator.translate(key, **kwargs)

def set_language(language: Language):
    """设置语言"""
    translator.set_language(language)

def get_language() -> Language:
    """获取当前语言"""
    return translator.get_language()
```

### 2. 翻译文件规范

```json
// locales/zh-CN.json
{
  "app": {
    "name": "第五人格命令行管理器",
    "version": "版本 {version}",
    "description": "第五人格游戏多渠道服和多账号管理工具"
  },
  "commands": {
    "account": {
      "name": "账号管理",
      "add": {
        "name": "添加账号",
        "description": "添加新的游戏账号",
        "usage": "dwrg account add --username <用户名> --server <渠道服> --password <密码>",
        "success": "账号添加成功",
        "error": "账号添加失败: {error}",
        "invalid_username": "用户名无效，长度必须在3-20字符之间",
        "invalid_server": "渠道服无效",
        "invalid_password": "密码无效，长度至少8位且必须包含大小写字母、数字和特殊字符"
      },
      "list": {
        "name": "列出账号",
        "description": "列出所有账号",
        "usage": "dwrg account list [--server <渠道服>]",
        "title": "账号列表",
        "no_accounts": "暂无账号",
        "account_info": "账号: {username} | 渠道服: {server} | 最后登录: {last_login}"
      },
      "switch": {
        "name": "切换账号",
        "description": "切换当前活动账号",
        "usage": "dwrg account switch <账号ID>",
        "success": "账号切换成功",
        "error": "账号切换失败: {error}",
        "account_not_found": "账号不存在"
      },
      "remove": {
        "name": "删除账号",
        "description": "删除指定账号",
        "usage": "dwrg account remove <账号ID>",
        "success": "账号删除成功",
        "error": "账号删除失败: {error}",
        "confirm": "确定要删除账号 {username} 吗？(y/N)"
      }
    },
    "server": {
      "name": "渠道服管理",
      "list": {
        "name": "列出渠道服",
        "description": "列出所有可用渠道服",
        "usage": "dwrg server list",
        "title": "渠道服列表",
        "no_servers": "暂无渠道服",
        "server_info": "渠道服: {name} | 状态: {status} | 版本: {version}"
      },
      "switch": {
        "name": "切换渠道服",
        "description": "切换当前渠道服",
        "usage": "dwrg server switch <渠道服名称>",
        "success": "渠道服切换成功",
        "error": "渠道服切换失败: {error}",
        "server_not_found": "渠道服不存在",
        "confirm": "确定要切换到 {server} 吗？(y/N)"
      },
      "info": {
        "name": "渠道服信息",
        "description": "显示渠道服详细信息",
        "usage": "dwrg server info <渠道服名称>",
        "title": "渠道服信息",
        "server_details": "名称: {name}\n显示名称: {display_name}\n地址: {endpoint}\n版本: {version}\n状态: {status}"
      }
    },
    "resource": {
      "name": "资源管理",
      "check": {
        "name": "检查资源",
        "description": "检查游戏文件完整性",
        "usage": "dwrg resource check",
        "title": "资源检查结果",
        "status": "状态: {status}",
        "files_checked": "已检查文件: {count}",
        "files_corrupted": "损坏文件: {count}",
        "files_missing": "缺失文件: {count}",
        "no_issues": "未发现问题",
        "issues_found": "发现问题，请使用 'dwrg resource repair' 修复"
      },
      "update": {
        "name": "更新资源",
        "description": "更新游戏资源",
        "usage": "dwrg resource update [--server <渠道服>]",
        "title": "资源更新",
        "checking": "检查更新...",
        "downloading": "下载更新...",
        "extracting": "解压文件...",
        "complete": "更新完成",
        "error": "更新失败: {error}"
      },
      "repair": {
        "name": "修复资源",
        "description": "修复游戏文件",
        "usage": "dwrg resource repair",
        "title": "资源修复",
        "repairing": "修复文件...",
        "complete": "修复完成",
        "error": "修复失败: {error}"
      }
    }
  },
  "messages": {
    "success": "操作成功",
    "error": "操作失败: {error}",
    "warning": "警告: {message}",
    "info": "信息: {message}",
    "loading": "加载中...",
    "processing": "处理中...",
    "complete": "完成"
  },
  "errors": {
    "file_not_found": "文件不存在: {path}",
    "permission_denied": "权限不足",
    "network_error": "网络错误: {error}",
    "invalid_input": "输入无效: {input}",
    "operation_timeout": "操作超时",
    "unknown_error": "未知错误: {error}"
  }
}
```

```json
// locales/en-US.json
{
  "app": {
    "name": "Identity V CLI Manager",
    "version": "Version {version}",
    "description": "A CLI tool for managing Identity V game servers and accounts"
  },
  "commands": {
    "account": {
      "name": "Account Management",
      "add": {
        "name": "Add Account",
        "description": "Add a new game account",
        "usage": "dwrg account add --username <username> --server <server> --password <password>",
        "success": "Account added successfully",
        "error": "Failed to add account: {error}",
        "invalid_username": "Invalid username, must be 3-20 characters",
        "invalid_server": "Invalid server",
        "invalid_password": "Invalid password, must be at least 8 characters with uppercase, lowercase, numbers and special characters"
      },
      "list": {
        "name": "List Accounts",
        "description": "List all accounts",
        "usage": "dwrg account list [--server <server>]",
        "title": "Account List",
        "no_accounts": "No accounts found",
        "account_info": "Account: {username} | Server: {server} | Last Login: {last_login}"
      },
      "switch": {
        "name": "Switch Account",
        "description": "Switch current active account",
        "usage": "dwrg account switch <account_id>",
        "success": "Account switched successfully",
        "error": "Failed to switch account: {error}",
        "account_not_found": "Account not found"
      },
      "remove": {
        "name": "Remove Account",
        "description": "Remove specified account",
        "usage": "dwrg account remove <account_id>",
        "success": "Account removed successfully",
        "error": "Failed to remove account: {error}",
        "confirm": "Are you sure you want to remove account {username}? (y/N)"
      }
    },
    "server": {
      "name": "Server Management",
      "list": {
        "name": "List Servers",
        "description": "List all available servers",
        "usage": "dwrg server list",
        "title": "Server List",
        "no_servers": "No servers found",
        "server_info": "Server: {name} | Status: {status} | Version: {version}"
      },
      "switch": {
        "name": "Switch Server",
        "description": "Switch current server",
        "usage": "dwrg server switch <server_name>",
        "success": "Server switched successfully",
        "error": "Failed to switch server: {error}",
        "server_not_found": "Server not found",
        "confirm": "Are you sure you want to switch to {server}? (y/N)"
      },
      "info": {
        "name": "Server Info",
        "description": "Show detailed server information",
        "usage": "dwrg server info <server_name>",
        "title": "Server Information",
        "server_details": "Name: {name}\nDisplay Name: {display_name}\nEndpoint: {endpoint}\nVersion: {version}\nStatus: {status}"
      }
    },
    "resource": {
      "name": "Resource Management",
      "check": {
        "name": "Check Resources",
        "description": "Check game file integrity",
        "usage": "dwrg resource check",
        "title": "Resource Check Results",
        "status": "Status: {status}",
        "files_checked": "Files Checked: {count}",
        "files_corrupted": "Corrupted Files: {count}",
        "files_missing": "Missing Files: {count}",
        "no_issues": "No issues found",
        "issues_found": "Issues found, please use 'dwrg resource repair' to fix"
      },
      "update": {
        "name": "Update Resources",
        "description": "Update game resources",
        "usage": "dwrg resource update [--server <server>]",
        "title": "Resource Update",
        "checking": "Checking for updates...",
        "downloading": "Downloading updates...",
        "extracting": "Extracting files...",
        "complete": "Update completed",
        "error": "Update failed: {error}"
      },
      "repair": {
        "name": "Repair Resources",
        "description": "Repair game files",
        "usage": "dwrg resource repair",
        "title": "Resource Repair",
        "repairing": "Repairing files...",
        "complete": "Repair completed",
        "error": "Repair failed: {error}"
      }
    }
  },
  "messages": {
    "success": "Operation successful",
    "error": "Operation failed: {error}",
    "warning": "Warning: {message}",
    "info": "Info: {message}",
    "loading": "Loading...",
    "processing": "Processing...",
    "complete": "Complete"
  },
  "errors": {
    "file_not_found": "File not found: {path}",
    "permission_denied": "Permission denied",
    "network_error": "Network error: {error}",
    "invalid_input": "Invalid input: {input}",
    "operation_timeout": "Operation timeout",
    "unknown_error": "Unknown error: {error}"
  }
}
```

### 3. 日期时间国际化

```python
# src/dwrg_manager/i18n/datetime_utils.py
import datetime
from typing import Optional, Union
from dwrg_manager.i18n.translator import translator, Language

class DateTimeFormatter:
    """日期时间格式化器"""
    
    def __init__(self):
        self.formatters = {
            Language.ZH_CN: self._format_zh_cn,
            Language.ZH_TW: self._format_zh_tw,
            Language.EN_US: self._format_en_us,
            Language.JA_JP: self._format_ja_jp,
            Language.KO_KR: self._format_ko_kr,
            Language.FR_FR: self._format_fr_fr,
            Language.DE_DE: self._format_de_de,
            Language.ES_ES: self._format_es_es,
            Language.RU_RU: self._format_ru_ru
        }
    
    def format_date(self, date: Union[datetime.date, datetime.datetime], 
                   format_type: str = "short") -> str:
        """格式化日期"""
        if isinstance(date, datetime.datetime):
            date = date.date()
        
        language = translator.get_language()
        formatter = self.formatters.get(language, self._format_en_us)
        return formatter.format_date(date, format_type)
    
    def format_time(self, time: Union[datetime.time, datetime.datetime], 
                   format_type: str = "short") -> str:
        """格式化时间"""
        if isinstance(time, datetime.datetime):
            time = time.time()
        
        language = translator.get_language()
        formatter = self.formatters.get(language, self._format_en_us)
        return formatter.format_time(time, format_type)
    
    def format_datetime(self, dt: datetime.datetime, 
                       format_type: str = "short") -> str:
        """格式化日期时间"""
        language = translator.get_language()
        formatter = self.formatters.get(language, self._format_en_us)
        return formatter.format_datetime(dt, format_type)
    
    def format_relative_time(self, dt: datetime.datetime) -> str:
        """格式化相对时间"""
        now = datetime.datetime.now()
        delta = now - dt
        
        if delta.days == 0:
            if delta.seconds < 60:
                return _("datetime.just_now")
            elif delta.seconds < 3600:
                minutes = delta.seconds // 60
                return _("datetime.minutes_ago", count=minutes)
            else:
                hours = delta.seconds // 3600
                return _("datetime.hours_ago", count=hours)
        elif delta.days == 1:
            return _("datetime.yesterday")
        elif delta.days < 7:
            return _("datetime.days_ago", count=delta.days)
        elif delta.days < 30:
            weeks = delta.days // 7
            return _("datetime.weeks_ago", count=weeks)
        elif delta.days < 365:
            months = delta.days // 30
            return _("datetime.months_ago", count=months)
        else:
            years = delta.days // 365
            return _("datetime.years_ago", count=years)
    
    def parse_date(self, date_str: str, format_type: str = "short") -> datetime.date:
        """解析日期字符串"""
        language = translator.get_language()
        formatter = self.formatters.get(language, self._format_en_us)
        return formatter.parse_date(date_str, format_type)
    
    def parse_time(self, time_str: str, format_type: str = "short") -> datetime.time:
        """解析时间字符串"""
        language = translator.get_language()
        formatter = self.formatters.get(language, self._format_en_us)
        return formatter.parse_time(time_str, format_type)
    
    def parse_datetime(self, dt_str: str, format_type: str = "short") -> datetime.datetime:
        """解析日期时间字符串"""
        language = translator.get_language()
        formatter = self.formatters.get(language, self._format_en_us)
        return formatter.parse_datetime(dt_str, format_type)

# 基础格式化器类
class BaseFormatter:
    """基础格式化器"""
    
    def format_date(self, date: datetime.date, format_type: str) -> str:
        """格式化日期"""
        if format_type == "short":
            return date.strftime("%Y-%m-%d")
        elif format_type == "medium":
            return date.strftime("%Y年%m月%d日")
        elif format_type == "long":
            return date.strftime("%Y年%m月%d日 %A")
        else:
            return date.strftime("%Y-%m-%d")
    
    def format_time(self, time: datetime.time, format_type: str) -> str:
        """格式化时间"""
        if format_type == "short":
            return time.strftime("%H:%M")
        elif format_type == "medium":
            return time.strftime("%H:%M:%S")
        elif format_type == "long":
            return time.strftime("%H:%M:%S %p")
        else:
            return time.strftime("%H:%M")
    
    def format_datetime(self, dt: datetime.datetime, format_type: str) -> str:
        """格式化日期时间"""
        date_part = self.format_date(dt.date(), "medium")
        time_part = self.format_time(dt.time(), "short")
        return f"{date_part} {time_part}"
    
    def parse_date(self, date_str: str, format_type: str) -> datetime.date:
        """解析日期字符串"""
        if format_type == "short":
            return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        elif format_type == "medium":
            return datetime.datetime.strptime(date_str, "%Y年%m月%d日").date()
        else:
            return datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    
    def parse_time(self, time_str: str, format_type: str) -> datetime.time:
        """解析时间字符串"""
        if format_type == "short":
            return datetime.datetime.strptime(time_str, "%H:%M").time()
        elif format_type == "medium":
            return datetime.datetime.strptime(time_str, "%H:%M:%S").time()
        else:
            return datetime.datetime.strptime(time_str, "%H:%M").time()
    
    def parse_datetime(self, dt_str: str, format_type: str) -> datetime.datetime:
        """解析日期时间字符串"""
        if format_type == "short":
            return datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
        elif format_type == "medium":
            return datetime.datetime.strptime(dt_str, "%Y年%m月%d日 %H:%M")
        else:
            return datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M")

# 各语言的格式化器实现
class ChineseFormatter(BaseFormatter):
    """中文格式化器"""
    
    def format_date(self, date: datetime.date, format_type: str) -> str:
        if format_type == "short":
            return date.strftime("%Y-%m-%d")
        elif format_type == "medium":
            return date.strftime("%Y年%m月%d日")
        elif format_type == "long":
            weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
            return date.strftime("%Y年%m月%d日 ") + weekdays[date.weekday()]
        else:
            return date.strftime("%Y-%m-%d")

class EnglishFormatter(BaseFormatter):
    """英文格式化器"""
    
    def format_date(self, date: datetime.date, format_type: str) -> str:
        if format_type == "short":
            return date.strftime("%Y-%m-%d")
        elif format_type == "medium":
            return date.strftime("%b %d, %Y")
        elif format_type == "long":
            return date.strftime("%B %d, %Y")
        else:
            return date.strftime("%Y-%m-%d")

# 实例化日期时间格式化器
datetime_formatter = DateTimeFormatter()
```

### 4. 数字和货币国际化

```python
# src/dwrg_manager/i18n/number_utils.py
import locale
from typing import Union, Optional
from dwrg_manager.i18n.translator import translator, Language

class NumberFormatter:
    """数字格式化器"""
    
    def __init__(self):
        self.formatters = {
            Language.ZH_CN: self._format_zh_cn,
            Language.ZH_TW: self._format_zh_tw,
            Language.EN_US: self._format_en_us,
            Language.JA_JP: self._format_ja_jp,
            Language.KO_KR: self._format_ko_kr,
            Language.FR_FR: self._format_fr_fr,
            Language.DE_DE: self._format_de_de,
            Language.ES_ES: self._format_es_es,
            Language.RU_RU: self._format_ru_ru
        }
        
        # 设置locale
        self._set_locale()
    
    def _set_locale(self):
        """设置locale"""
        try:
            language = translator.get_language()
            locale_map = {
                Language.ZH_CN: 'zh_CN.UTF-8',
                Language.ZH_TW: 'zh_TW.UTF-8',
                Language.EN_US: 'en_US.UTF-8',
                Language.JA_JP: 'ja_JP.UTF-8',
                Language.KO_KR: 'ko_KR.UTF-8',
                Language.FR_FR: 'fr_FR.UTF-8',
                Language.DE_DE: 'de_DE.UTF-8',
                Language.ES_ES: 'es_ES.UTF-8',
                Language.RU_RU: 'ru_RU.UTF-8'
            }
            
            target_locale = locale_map.get(language, 'en_US.UTF-8')
            locale.setlocale(locale.LC_ALL, target_locale)
        except locale.Error:
            locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    
    def format_number(self, number: Union[int, float], 
                     decimal_places: int = 0) -> str:
        """格式化数字"""
        language = translator.get_language()
        formatter = self.formatters.get(language, self._format_en_us)
        return formatter.format_number(number, decimal_places)
    
    def format_decimal(self, number: Union[int, float], 
                      decimal_places: int = 2) -> str:
        """格式化小数"""
        language = translator.get_language()
        formatter = self.formatters.get(language, self._format_en_us)
        return formatter.format_decimal(number, decimal_places)
    
    def format_percentage(self, number: Union[int, float], 
                         decimal_places: int = 1) -> str:
        """格式化百分比"""
        language = translator.get_language()
        formatter = self.formatters.get(language, self._format_en_us)
        return formatter.format_percentage(number, decimal_places)
    
    def format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        size = float(size_bytes)
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1
        
        language = translator.get_language()
        formatter = self.formatters.get(language, self._format_en_us)
        return formatter.format_file_size(size, units[unit_index])
    
    def format_currency(self, amount: Union[int, float], 
                       currency_code: str = None) -> str:
        """格式化货币"""
        if currency_code is None:
            language = translator.get_language()
            locale_info = translator.get_locale(language)
            currency_code = locale_info.currency
        
        language = translator.get_language()
        formatter = self.formatters.get(language, self._format_en_us)
        return formatter.format_currency(amount, currency_code)
    
    def parse_number(self, number_str: str) -> Union[int, float]:
        """解析数字字符串"""
        language = translator.get_language()
        formatter = self.formatters.get(language, self._format_en_us)
        return formatter.parse_number(number_str)
    
    def parse_currency(self, currency_str: str, 
                      currency_code: str = None) -> float:
        """解析货币字符串"""
        language = translator.get_language()
        formatter = self.formatters.get(language, self._format_en_us)
        return formatter.parse_currency(currency_str, currency_code)

# 基础格式化器类
class BaseNumberFormatter:
    """基础数字格式化器"""
    
    def format_number(self, number: Union[int, float], decimal_places: int) -> str:
        """格式化数字"""
        if isinstance(number, int):
            return f"{number:,}"
        else:
            return f"{number:,.{decimal_places}f}"
    
    def format_decimal(self, number: Union[int, float], decimal_places: int) -> str:
        """格式化小数"""
        return f"{number:,.{decimal_places}f}"
    
    def format_percentage(self, number: Union[int, float], decimal_places: int) -> str:
        """格式化百分比"""
        return f"{number * 100:.{decimal_places}f}%"
    
    def format_file_size(self, size: float, unit: str) -> str:
        """格式化文件大小"""
        return f"{size:.1f} {unit}"
    
    def format_currency(self, amount: Union[int, float], currency_code: str) -> str:
        """格式化货币"""
        return f"{amount:,.2f} {currency_code}"
    
    def parse_number(self, number_str: str) -> Union[int, float]:
        """解析数字字符串"""
        try:
            # 移除千位分隔符
            clean_str = number_str.replace(',', '').replace(' ', '')
            if '.' in clean_str:
                return float(clean_str)
            else:
                return int(clean_str)
        except ValueError:
            raise ValueError(f"Invalid number format: {number_str}")
    
    def parse_currency(self, currency_str: str, currency_code: str) -> float:
        """解析货币字符串"""
        try:
            # 移除货币符号和千位分隔符
            clean_str = currency_str.replace(currency_code, '').replace(',', '').replace(' ', '').strip()
            return float(clean_str)
        except ValueError:
            raise ValueError(f"Invalid currency format: {currency_str}")

# 各语言的格式化器实现
class ChineseFormatter(BaseNumberFormatter):
    """中文数字格式化器"""
    
    def format_number(self, number: Union[int, float], decimal_places: int) -> str:
        if isinstance(number, int):
            return f"{number:,}".replace(',', ',')
        else:
            return f"{number:,.{decimal_places}f}".replace(',', ',')
    
    def format_currency(self, amount: Union[int, float], currency_code: str) -> str:
        if currency_code == "CNY":
            return f"¥{amount:,.2f}"
        elif currency_code == "TWD":
            return f"NT${amount:,.2f}"
        else:
            return f"{amount:,.2f} {currency_code}"

class EnglishFormatter(BaseNumberFormatter):
    """英文数字格式化器"""
    
    def format_currency(self, amount: Union[int, float], currency_code: str) -> str:
        if currency_code == "USD":
            return f"${amount:,.2f}"
        elif currency_code == "EUR":
            return f"€{amount:,.2f}"
        elif currency_code == "JPY":
            return f"¥{amount:,.0f}"
        elif currency_code == "KRW":
            return f"₩{amount:,.0f}"
        else:
            return f"{amount:,.2f} {currency_code}"

# 实例化数字格式化器
number_formatter = NumberFormatter()
```

## 国际化测试规范

### 1. 翻译测试

```python
# tests/i18n/test_translator.py
import pytest
from pathlib import Path
from dwrg_manager.i18n.translator import Translator, Language, _

class TestTranslator:
    """翻译器测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.translator = Translator()
    
    def test_language_switching(self):
        """测试语言切换"""
        # 切换到英语
        self.translator.set_language(Language.EN_US)
        assert self.translator.get_language() == Language.EN_US
        
        # 切换到中文
        self.translator.set_language(Language.ZH_CN)
        assert self.translator.get_language() == Language.ZH_CN
    
    def test_translation(self):
        """测试翻译功能"""
        # 设置中文
        self.translator.set_language(Language.ZH_CN)
        
        # 测试简单翻译
        assert _("app.name") == "第五人格命令行管理器"
        
        # 测试带参数的翻译
        result = _("commands.account.add.success")
        assert result == "账号添加成功"
        
        # 设置英文
        self.translator.set_language(Language.EN_US)
        
        # 测试英文翻译
        assert _("app.name") == "Identity V CLI Manager"
        
        # 测试带参数的翻译
        result = _("commands.account.add.success")
        assert result == "Account added successfully"
    
    def test_fallback_translation(self):
        """测试回退翻译"""
        # 设置不存在的语言
        self.translator.set_language(Language("zh-CN"))
        
        # 测试回退到英文
        result = _("app.name")
        assert result == "Identity V CLI Manager"
    
    def test_locale_info(self):
        """测试语言环境信息"""
        # 获取中文环境信息
        self.translator.set_language(Language.ZH_CN)
        locale_info = self.translator.get_current_locale_info()
        
        assert locale_info['language'] == 'zh-CN'
        assert locale_info['display_name'] == '简体中文'
        assert locale_info['country'] == '中国'
        assert locale_info['currency'] == 'CNY'
        
        # 获取英文环境信息
        self.translator.set_language(Language.EN_US)
        locale_info = self.translator.get_current_locale_info()
        
        assert locale_info['language'] == 'en-US'
        assert locale_info['display_name'] == 'English'
        assert locale_info['country'] == 'United States'
        assert locale_info['currency'] == 'USD'
    
    def test_available_languages(self):
        """测试可用语言列表"""
        languages = self.translator.get_available_languages()
        
        assert Language.ZH_CN in languages
        assert Language.EN_US in languages
        assert Language.JA_JP in languages
        assert len(languages) == 9
```

### 2. 日期时间测试

```python
# tests/i18n/test_datetime.py
import pytest
import datetime
from dwrg_manager.i18n.datetime_utils import datetime_formatter

class TestDateTimeFormatter:
    """日期时间格式化器测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.test_date = datetime.date(2026, 9, 21)
        self.test_time = datetime.time(14, 30, 45)
        self.test_datetime = datetime.datetime(2026, 9, 21, 14, 30, 45)
    
    def test_chinese_date_formatting(self):
        """测试中文日期格式化"""
        # 设置中文
        from dwrg_manager.i18n.translator import set_language, Language
        set_language(Language.ZH_CN)
        
        # 短格式
        result = datetime_formatter.format_date(self.test_date, "short")
        assert result == "2026-09-21"
        
        # 中等格式
        result = datetime_formatter.format_date(self.test_date, "medium")
        assert result == "2026年09月21日"
        
        # 长格式
        result = datetime_formatter.format_date(self.test_date, "long")
        assert "2026年09月21日" in result
        assert "星期" in result
    
    def test_english_date_formatting(self):
        """测试英文日期格式化"""
        # 设置英文
        from dwrg_manager.i18n.translator import set_language, Language
        set_language(Language.EN_US)
        
        # 短格式
        result = datetime_formatter.format_date(self.test_date, "short")
        assert result == "2026-09-21"
        
        # 中等格式
        result = datetime_formatter.format_date(self.test_date, "medium")
        assert "Sep" in result or "Sep" in result
        assert "21, 2026" in result
    
    def test_time_formatting(self):
        """测试时间格式化"""
        # 设置中文
        from dwrg_manager.i18n.translator import set_language, Language
        set_language(Language.ZH_CN)
        
        # 短格式
        result = datetime_formatter.format_time(self.test_time, "short")
        assert result == "14:30"
        
        # 中等格式
        result = datetime_formatter.format_time(self.test_time, "medium")
        assert result == "14:30:45"
    
    def test_datetime_formatting(self):
        """测试日期时间格式化"""
        # 设置英文
        from dwrg_manager.i18n.translator import set_language, Language
        set_language(Language.EN_US)
        
        result = datetime_formatter.format_datetime(self.test_datetime, "medium")
        assert "2026" in result
        assert "Sep" in result or "Sep" in result
        assert "14:30" in result
    
    def test_relative_time_formatting(self):
        """测试相对时间格式化"""
        # 设置中文
        from dwrg_manager.i18n.translator import set_language, Language
        set_language(Language.ZH_CN)
        
        # 创建一个相对时间
        past_datetime = datetime.datetime.now() - datetime.timedelta(hours=2)
        
        result = datetime_formatter.format_relative_time(past_datetime)
        assert "小时前" in result
        
        # 创建一个相对时间
        past_datetime = datetime.datetime.now() - datetime.timedelta(days=1)
        
        result = datetime_formatter.format_relative_time(past_datetime)
        assert result == "昨天"
```

### 3. 数字格式化测试

```python
# tests/i18n/test_numbers.py
import pytest
from dwrg_manager.i18n.number_utils import number_formatter

class TestNumberFormatter:
    """数字格式化器测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.test_number = 1234567.8912
    
    def test_chinese_number_formatting(self):
        """测试中文数字格式化"""
        # 设置中文
        from dwrg_manager.i18n.translator import set_language, Language
        set_language(Language.ZH_CN)
        
        # 整数格式化
        result = number_formatter.format_number(1234567)
        assert "1,234,567" in result
        
        # 小数格式化
        result = number_formatter.format_decimal(1234.5678, 2)
        assert "1,234.57" in result
        
        # 百分比格式化
        result = number_formatter.format_percentage(0.1234, 1)
        assert "12.3%" in result
        
        # 文件大小格式化
        result = number_formatter.format_file_size(1024 * 1024)
        assert "1.0 MB" in result
        
        # 货币格式化
        result = number_formatter.format_currency(1234.56, "CNY")
        assert "¥1,234.56" in result
    
    def test_english_number_formatting(self):
        """测试英文数字格式化"""
        # 设置英文
        from dwrg_manager.i18n.translator import set_language, Language
        set_language(Language.EN_US)
        
        # 整数格式化
        result = number_formatter.format_number(1234567)
        assert "1,234,567" in result
        
        # 小数格式化
        result = number_formatter.format_decimal(1234.5678, 2)
        assert "1,234.57" in result
        
        # 货币格式化
        result = number_formatter.format_currency(1234.56, "USD")
        assert "$1,234.56" in result
    
    def test_number_parsing(self):
        """测试数字解析"""
        # 设置中文
        from dwrg_manager.i18n.translator import set_language, Language
        set_language(Language.ZH_CN)
        
        # 解析整数
        result = number_formatter.parse_number("1,234,567")
        assert result == 1234567
        
        # 解析小数
        result = number_formatter.parse_number("1,234.56")
        assert result == 1234.56
        
        # 解析货币
        result = number_formatter.parse_currency("¥1,234.56", "CNY")
        assert result == 1234.56
```

## 国际化部署规范

### 1. 翻译文件管理

```bash
# 翻译文件管理脚本
#!/bin/bash

# 检查翻译文件完整性
check_translations() {
    echo "检查翻译文件完整性..."
    
    for lang_file in locales/*.json; do
        if [ -f "$lang_file" ]; then
            # 检查JSON语法
            if ! jq empty "$lang_file" 2>/dev/null; then
                echo "错误: $lang_file 语法错误"
                exit 1
            fi
            
            # 检查必需的键
            if ! jq -e '.app.name' "$lang_file" >/dev/null; then
                echo "错误: $lang_file 缺少必需的键: app.name"
                exit 1
            fi
            
            echo "✓ $lang_file 格式正确"
        fi
    done
    
    echo "所有翻译文件检查通过"
}

# 提取需要翻译的文本
extract_strings() {
    echo "提取需要翻译的文本..."
    
    # 创建临时目录
    mkdir -p temp/extract
    
    # 使用pybabel提取字符串
    pybabel extract -F babel.cfg -k _ -o temp/extract/messages.pot src/
    
    echo "文本提取完成: temp/extract/messages.pot"
}

# 初始化新语言
init_language() {
    local lang_code=$1
    local lang_name=$2
    
    if [ -z "$lang_code" ] || [ -z "$lang_name" ]; then
        echo "使用方法: init_language <语言代码> <语言名称>"
        exit 1
    fi
    
    echo "初始化新语言: $lang_name ($lang_code)"
    
    # 使用pybabel初始化新语言
    pybabel init -i temp/extract/messages.pot -d locales/ -l $lang_code
    
    echo "语言 $lang_name 初始化完成"
}

# 更新翻译文件
update_translations() {
    echo "更新翻译文件..."
    
    # 使用pybabel更新翻译文件
    pybabel update -i temp/extract/messages.pot -d locales/
    
    echo "翻译文件更新完成"
}

# 验证翻译完整性
validate_translations() {
    echo "验证翻译完整性..."
    
    for lang_file in locales/*.json; do
        if [ -f "$lang_file" ]; then
            lang_code=$(basename "$lang_file" .json)
            
            # 检查是否有未翻译的键
            untranslated=$(jq -r '. | to_entries | map(select(.value == "" or .value | startswith("TODO"))) | length' "$lang_file")
            
            if [ "$untranslated" -gt 0 ]; then
                echo "警告: $lang_code 有 $untranslated 个未翻译的键"
            else
                echo "✓ $lang_code 翻译完整"
            fi
        fi
    done
}

# 主菜单
case "$1" in
    "check")
        check_translations
        ;;
    "extract")
        extract_strings
        ;;
    "init")
        init_language "$2" "$3"
        ;;
    "update")
        update_translations
        ;;
    "validate")
        validate_translations
        ;;
    *)
        echo "使用方法: $0 {check|extract|init|update|validate}"
        echo "  check    - 检查翻译文件完整性"
        echo "  extract  - 提取需要翻译的文本"
        echo "  init     - 初始化新语言 (init <语言代码> <语言名称>)"
        echo "  update   - 更新翻译文件"
        echo "  validate - 验证翻译完整性"
        exit 1
        ;;
esac
```

### 2. 国际化测试脚本

```python
# scripts/test_i18n.py
"""
国际化测试脚本
"""
import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Any

def check_translation_files():
    """检查翻译文件完整性"""
    locale_dir = Path("locales")
    if not locale_dir.exists():
        print("错误: locales 目录不存在")
        return False
    
    issues = []
    
    # 检查每个语言文件
    for lang_file in locale_dir.glob("*.json"):
        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                translations = json.load(f)
            
            # 检查必需的键
            required_keys = ["app", "commands", "messages", "errors"]
            for key in required_keys:
                if key not in translations:
                    issues.append(f"{lang_file.name}: 缺少必需的键: {key}")
            
            # 检查空值
            def check_empty_values(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}" if path else key
                        if value == "":
                            issues.append(f"{lang_file.name}: 空值: {current_path}")
                        elif isinstance(value, dict):
                            check_empty_values(value, current_path)
                        elif isinstance(value, list):
                            for i, item in enumerate(value):
                                if isinstance(item, dict):
                                    check_empty_values(item, f"{current_path}[{i}]")
            
            check_empty_values(translations)
            
        except json.JSONDecodeError as e:
            issues.append(f"{lang_file.name}: JSON 语法错误: {e}")
        except Exception as e:
            issues.append(f"{lang_file.name}: 错误: {e}")
    
    if issues:
        print("发现以下问题:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("✓ 所有翻译文件检查通过")
        return True

def check_translation_consistency():
    """检查翻译一致性"""
    locale_dir = Path("locales")
    if not locale_dir.exists():
        print("错误: locales 目录不存在")
        return False
    
    # 加载所有翻译文件
    translations = {}
    for lang_file in locale_dir.glob("*.json"):
        lang_code = lang_file.stem
        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                translations[lang_code] = json.load(f)
        except Exception:
            continue
    
    if len(translations) < 2:
        print("警告: 需要至少两种语言来检查一致性")
        return True
    
    # 检查键的一致性
    reference_lang = list(translations.keys())[0]
    reference_keys = set()
    
    def collect_keys(obj, path=""):
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_path = f"{path}.{key}" if path else key
                reference_keys.add(current_path)
                if isinstance(value, dict):
                    collect_keys(value, current_path)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            collect_keys(item, current_path)
    
    collect_keys(translations[reference_lang])
    
    # 检查其他语言是否包含所有键
    consistency_issues = []
    for lang_code, translation in translations.items():
        if lang_code == reference_lang:
            continue
        
        current_keys = set()
        collect_keys(translation)
        
        missing_keys = reference_keys - current_keys
        extra_keys = current_keys - reference_keys
        
        if missing_keys:
            consistency_issues.append(f"{lang_code}: 缺少键: {', '.join(sorted(missing_keys))}")
        if extra_keys:
            consistency_issues.append(f"{lang_code}: 多余键: {', '.join(sorted(extra_keys))}")
    
    if consistency_issues:
        print("发现以下一致性问题:")
        for issue in consistency_issues:
            print(f"  - {issue}")
        return False
    else:
        print("✓ 所有翻译文件键值一致")
        return True

def test_translation_coverage():
    """测试翻译覆盖率"""
    locale_dir = Path("locales")
    if not locale_dir.exists():
        print("错误: locales 目录不存在")
        return False
    
    # 统计翻译覆盖率
    coverage_stats = {}
    
    for lang_file in locale_dir.glob("*.json"):
        lang_code = lang_file.stem
        
        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                translation = json.load(f)
            
            def count_translations(obj):
                count = 0
                if isinstance(obj, dict):
                    for value in obj.values():
                        if isinstance(value, str):
                            count += 1
                            if value == "":
                                count -= 1  # 不计算空值
                        elif isinstance(value, dict):
                            count += count_translations(value)
                        elif isinstance(value, list):
                            for item in value:
                                if isinstance(item, dict):
                                    count += count_translations(item)
                return count
            
            total_keys = count_translations(translation)
            empty_keys = translation.get("_empty_keys", 0)  # 假设有统计空值的字段
            
            coverage_stats[lang_code] = {
                "total_keys": total_keys,
                "translated_keys": total_keys - empty_keys,
                "coverage": ((total_keys - empty_keys) / total_keys * 100) if total_keys > 0 else 0
            }
            
        except Exception:
            continue
    
    print("翻译覆盖率统计:")
    for lang_code, stats in coverage_stats.items():
        print(f"  {lang_code}: {stats['coverage']:.1f}% ({stats['translated_keys']}/{stats['total_keys']})")
    
    # 检查是否所有语言的覆盖率都达到要求
    min_coverage = 90.0
    low_coverage = [lang for lang, stats in coverage_stats.items() if stats['coverage'] < min_coverage]
    
    if low_coverage:
        print(f"警告: 以下语言覆盖率低于 {min_coverage}%: {', '.join(low_coverage)}")
        return False
    else:
        print(f"✓ 所有语言覆盖率都达到 {min_coverage}% 以上")
        return True

def main():
    """主函数"""
    print("开始国际化测试...")
    
    # 运行所有测试
    tests = [
        ("翻译文件完整性", check_translation_files),
        ("翻译一致性", check_translation_consistency),
        ("翻译覆盖率", test_translation_coverage)
    ]
    
    all_passed = True
    for test_name, test_func in tests:
        print(f"\n运行测试: {test_name}")
        if not test_func():
            all_passed = False
    
    print("\n" + "="*50)
    if all_passed:
        print("✓ 所有国际化测试通过")
        sys.exit(0)
    else:
        print("✗ 部分国际化测试失败")
        sys.exit(1)

if __name__ == "__main__":
    main()
```

这个国际化标准文档提供了完整的国际化实现指南，确保项目能够支持多语言、多地区的用户需求。