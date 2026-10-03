---
name: plugin-system-standards-dwrg
description: 第五人格命令行管理器的插件系统标准和规范
metadata:
  node_type: memory
  type: project
  created_date: 2026-09-21
  status: active
  originSessionId: sess_30048853-8656-4451-96f5-dd221dfd42ae
---

# 插件系统标准和规范 - 第五人格命令行管理器

## 插件系统理念

基于Vibe Coding理念，我们将插件系统作为项目扩展的核心机制，确保工具能够灵活适应不同用户的需求。采用模块化、可扩展的插件架构，支持第三方开发者贡献功能。

## 插件系统架构

### 1. 插件层次模型

```
┌─────────────────────────────────────────────────────┐
│                   应用层                             │
│  • 主应用  • 插件管理器  • 插件加载器  • 插件API     │
├─────────────────────────────────────────────────────┤
│                   插件层                             │
│  • 核心插件  • 第三方插件  • 用户自定义插件  • 扩展包   │
├─────────────────────────────────────────────────────┤
│                   接口层                             │
│  • 插件接口  • 生命周期钩子  • 事件系统  • 数据模型   │
├─────────────────────────────────────────────────────┤
│                   基础层                             │
│  • 文件系统  • 配置管理  • 日志系统  • 安全机制     │
└─────────────────────────────────────────────────────┘
```

### 2. 插件类型

| 插件类型 | 用途 | 示例 | 生命周期 |
|---------|------|------|----------|
| 命令插件 | 添加新的CLI命令 | 账号同步插件、服务器检测插件 | 启动时加载 |
| 功能插件 | 扩展核心功能 | 自动更新插件、备份插件 | 按需加载 |
| 界面插件 | 扩展用户界面 | 主题插件、界面增强插件 | 启动时加载 |
| 数据插件 | 处理特定数据格式 | 游戏数据解析插件、配置转换插件 | 按需加载 |
| 集成插件 | 与外部系统集成 | 社交媒体集成、云存储插件 | 按需加载 |

## 插件接口规范

### 1. 插件基础接口

```python
# src/dwrg_manager/plugins/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type, Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

class PluginStatus(Enum):
    """插件状态"""
    UNLOADED = "unloaded"
    LOADED = "loaded"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"

@dataclass
class PluginInfo:
    """插件信息"""
    name: str
    version: str
    description: str
    author: str
    email: Optional[str] = None
    website: Optional[str] = None
    license: Optional[str] = None
    dependencies: List[str] = None
    min_app_version: Optional[str] = None
    max_app_version: Optional[str] = None
    tags: List[str] = None
    category: str = "general"
    icon: Optional[str] = None

@dataclass
class PluginManifest:
    """插件清单"""
    info: PluginInfo
    entry_point: str
    config_schema: Optional[Dict[str, Any]] = None
    permissions: List[str] = None
    resources: List[str] = None
    hooks: Dict[str, List[str]] = None
    commands: Dict[str, Dict[str, Any]] = None

class PluginInterface(ABC):
    """插件接口基类"""
    
    def __init__(self, plugin_manager):
        self.plugin_manager = plugin_manager
        self.status = PluginStatus.UNLOADED
        self.config = {}
        self.logger = None
        
    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """获取插件信息"""
        pass
    
    @property
    def manifest(self) -> PluginManifest:
        """获取插件清单"""
        return PluginManifest(
            info=self.info,
            entry_point=self.__class__.__name__,
            permissions=self.get_permissions(),
            resources=self.get_resources(),
            hooks=self.get_hooks(),
            commands=self.get_commands()
        )
    
    def get_permissions(self) -> List[str]:
        """获取插件所需的权限"""
        return []
    
    def get_resources(self) -> List[str]:
        """获取插件所需的资源"""
        return []
    
    def get_hooks(self) -> Dict[str, List[str]]:
        """获取插件注册的钩子"""
        return {}
    
    def get_commands(self) -> Dict[str, Dict[str, Any]]:
        """获取插件注册的命令"""
        return {}
    
    def set_config(self, config: Dict[str, Any]):
        """设置插件配置"""
        self.config = config
    
    def get_config(self) -> Dict[str, Any]:
        """获取插件配置"""
        return self.config
    
    def set_logger(self, logger):
        """设置日志器"""
        self.logger = logger
    
    def log(self, level: str, message: str, **kwargs):
        """记录日志"""
        if self.logger:
            getattr(self.logger, level.lower())(message, **kwargs)
    
    # 生命周期方法
    def on_load(self) -> bool:
        """插件加载时调用"""
        self.log("info", f"插件 {self.info.name} 开始加载")
        return True
    
    def on_unload(self) -> bool:
        """插件卸载时调用"""
        self.log("info", f"插件 {self.info.name} 开始卸载")
        return True
    
    def on_activate(self) -> bool:
        """插件激活时调用"""
        self.log("info", f"插件 {self.info.name} 开始激活")
        return True
    
    def on_deactivate(self) -> bool:
        """插件停用时调用"""
        self.log("info", f"插件 {self.info.name} 开始停用")
        return True
    
    def on_enable(self) -> bool:
        """插件启用时调用"""
        return True
    
    def on_disable(self) -> bool:
        """插件禁用时调用"""
        return True
    
    # 事件处理方法
    def on_event(self, event_type: str, data: Dict[str, Any]) -> Any:
        """处理事件"""
        return None
    
    # 命令处理方法
    def handle_command(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """处理命令"""
        return {"success": False, "error": "Command not implemented"}
```

### 2. 插件管理器

```python
# src/dwrg_manager/plugins/manager.py
import os
import sys
import importlib
import importlib.util
import inspect
from typing import Dict, List, Optional, Type, Any
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
import json

from dwrg_manager.plugins.base import PluginInterface, PluginInfo, PluginManifest, PluginStatus
from dwrg_manager.utils.logger import logger
from dwrg_manager.config.manager import ConfigManager

class PluginLoadError(Exception):
    """插件加载错误"""
    pass

class PluginActivateError(Exception):
    """插件激活错误"""
    pass

@dataclass
class PluginInstance:
    """插件实例"""
    plugin_class: Type[PluginInterface]
    instance: PluginInterface
    status: PluginStatus
    manifest: PluginManifest
    config: Dict[str, Any]
    dependencies: List[str]
    loaded_at: float
    activated_at: Optional[float] = None

class PluginManager:
    """插件管理器"""
    
    def __init__(self, config_manager: ConfigManager, plugin_dir: Path = None):
        self.config_manager = config_manager
        self.plugin_dir = plugin_dir or Path.home() / '.dwrg-cli' / 'plugins'
        self.plugin_dir.mkdir(parents=True, exist_ok=True)
        
        # 插件存储
        self.plugins: Dict[str, PluginInstance] = {}
        self.loaded_plugins: Dict[str, PluginInstance] = {}
        self.active_plugins: Dict[str, PluginInstance] = {}
        
        # 事件系统
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        # 配置
        self.plugin_config = self.config_manager.get_plugin_config()
        
        # 初始化
        self._init_plugin_directories()
        self._load_builtin_plugins()
    
    def _init_plugin_directories(self):
        """初始化插件目录"""
        # 创建插件子目录
        subdirs = ['core', 'third-party', 'user']
        for subdir in subdirs:
            (self.plugin_dir / subdir).mkdir(exist_ok=True)
    
    def _load_builtin_plugins(self):
        """加载内置插件"""
        builtin_dir = Path(__file__).parent / 'builtin'
        if builtin_dir.exists():
            self.load_plugins_from_directory(builtin_dir)
    
    def load_plugins_from_directory(self, directory: Path) -> List[str]:
        """从目录加载插件"""
        loaded_plugins = []
        
        if not directory.exists():
            return loaded_plugins
        
        for plugin_file in directory.glob('*.py'):
            if plugin_file.name.startswith('_'):
                continue
            
            try:
                plugin_name = self.load_plugin(plugin_file)
                if plugin_name:
                    loaded_plugins.append(plugin_name)
            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_file}: {e}")
        
        return loaded_plugins
    
    def load_plugin(self, plugin_path: Path) -> Optional[str]:
        """加载单个插件"""
        try:
            # 动态导入插件模块
            spec = importlib.util.spec_from_file_location(
                plugin_path.stem, 
                plugin_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # 查找插件类
            plugin_classes = []
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) and 
                    issubclass(obj, PluginInterface) and 
                    obj != PluginInterface):
                    plugin_classes.append(obj)
            
            if not plugin_classes:
                raise PluginLoadError(f"No plugin class found in {plugin_path}")
            
            # 使用第一个找到的插件类
            plugin_class = plugin_classes[0]
            
            # 创建插件实例
            plugin_instance = plugin_class(self)
            
            # 验证插件信息
            if not hasattr(plugin_instance, 'info'):
                raise PluginLoadError(f"Plugin {plugin_path} missing info property")
            
            plugin_info = plugin_instance.info
            
            # 检查版本兼容性
            if not self._check_version_compatibility(plugin_info):
                raise PluginLoadError(f"Version incompatible: {plugin_info.name}")
            
            # 检查依赖
            if not self._check_dependencies(plugin_info.dependencies or []):
                raise PluginLoadError(f"Dependencies not satisfied: {plugin_info.name}")
            
            # 加载插件
            if plugin_instance.on_load():
                plugin_instance.status = PluginStatus.LOADED
                
                # 创建插件实例记录
                plugin_manifest = plugin_instance.manifest
                plugin_config = self.plugin_config.get(plugin_info.name, {})
                
                plugin_record = PluginInstance(
                    plugin_class=plugin_class,
                    instance=plugin_instance,
                    status=PluginStatus.LOADED,
                    manifest=plugin_manifest,
                    config=plugin_config,
                    dependencies=plugin_info.dependencies or [],
                    loaded_at=time.time()
                )
                
                # 存储插件
                self.plugins[plugin_info.name] = plugin_record
                self.loaded_plugins[plugin_info.name] = plugin_record
                
                # 记录日志
                logger.info(f"Plugin loaded: {plugin_info.name} v{plugin_info.version}")
                
                return plugin_info.name
            else:
                raise PluginLoadError(f"Failed to load plugin: {plugin_info.name}")
                
        except Exception as e:
            logger.error(f"Error loading plugin {plugin_path}: {e}")
            raise PluginLoadError(f"Failed to load plugin {plugin_path}: {e}")
    
    def _check_version_compatibility(self, plugin_info: PluginInfo) -> bool:
        """检查版本兼容性"""
        app_version = "1.0.0"  # 从配置获取
        
        if plugin_info.min_app_version:
            if self._compare_versions(app_version, plugin_info.min_app_version) < 0:
                return False
        
        if plugin_info.max_app_version:
            if self._compare_versions(app_version, plugin_info.max_app_version) > 0:
                return False
        
        return True
    
    def _check_dependencies(self, dependencies: List[str]) -> bool:
        """检查依赖"""
        for dep in dependencies:
            if dep not in self.loaded_plugins:
                return False
        return True
    
    def _compare_versions(self, version1: str, version2: str) -> int:
        """比较版本号"""
        def normalize_version(v):
            return [int(x) for x in v.split('.')]
        
        v1 = normalize_version(version1)
        v2 = normalize_version(version2)
        
        for i in range(max(len(v1), len(v2))):
            n1 = v1[i] if i < len(v1) else 0
            n2 = v2[i] if i < len(v2) else 0
            
            if n1 < n2:
                return -1
            elif n1 > n2:
                return 1
        
        return 0
    
    def activate_plugin(self, plugin_name: str) -> bool:
        """激活插件"""
        if plugin_name not in self.loaded_plugins:
            raise PluginActivateError(f"Plugin {plugin_name} not loaded")
        
        plugin_record = self.loaded_plugins[plugin_name]
        
        if plugin_record.status == PluginStatus.ACTIVE:
            return True
        
        try:
            # 激活插件
            if plugin_record.instance.on_activate():
                plugin_record.status = PluginStatus.ACTIVE
                plugin_record.activated_at = time.time()
                
                # 添加到活动插件
                self.active_plugins[plugin_name] = plugin_record
                
                # 注册钩子和命令
                self._register_plugin_hooks(plugin_record)
                self._register_plugin_commands(plugin_record)
                
                logger.info(f"Plugin activated: {plugin_name}")
                return True
            else:
                raise PluginActivateError(f"Failed to activate plugin: {plugin_name}")
                
        except Exception as e:
            logger.error(f"Error activating plugin {plugin_name}: {e}")
            raise PluginActivateError(f"Failed to activate plugin {plugin_name}: {e}")
    
    def deactivate_plugin(self, plugin_name: str) -> bool:
        """停用插件"""
        if plugin_name not in self.active_plugins:
            return True
        
        plugin_record = self.active_plugins[plugin_name]
        
        try:
            # 停用插件
            if plugin_record.instance.on_deactivate():
                plugin_record.status = PluginStatus.INACTIVE
                
                # 从活动插件移除
                del self.active_plugins[plugin_name]
                
                # 注销钩子和命令
                self._unregister_plugin_hooks(plugin_record)
                self._unregister_plugin_commands(plugin_record)
                
                logger.info(f"Plugin deactivated: {plugin_name}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error deactivating plugin {plugin_name}: {e}")
            return False
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """卸载插件"""
        if plugin_name not in self.plugins:
            return True
        
        plugin_record = self.plugins[plugin_name]
        
        # 先停用插件
        if plugin_name in self.active_plugins:
            self.deactivate_plugin(plugin_name)
        
        try:
            # 卸载插件
            if plugin_record.instance.on_unload():
                # 移除插件记录
                if plugin_name in self.loaded_plugins:
                    del self.loaded_plugins[plugin_name]
                if plugin_name in self.plugins:
                    del self.plugins[plugin_name]
                
                logger.info(f"Plugin unloaded: {plugin_name}")
                return True
            else:
                return False
                
        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_name}: {e}")
            return False
    
    def _register_plugin_hooks(self, plugin_record: PluginInstance):
        """注册插件钩子"""
        hooks = plugin_record.manifest.hooks or {}
        
        for event_type, handler_names in hooks.items():
            for handler_name in handler_names:
                if handler_name in plugin_record.instance.__dict__:
                    handler = getattr(plugin_record.instance, handler_name)
                    self.register_event_handler(event_type, handler)
    
    def _unregister_plugin_hooks(self, plugin_record: PluginInstance):
        """注销插件钩子"""
        hooks = plugin_record.manifest.hooks or {}
        
        for event_type, handler_names in hooks.items():
            for handler_name in handler_names:
                if handler_name in plugin_record.instance.__dict__:
                    handler = getattr(plugin_record.instance, handler_name)
                    self.unregister_event_handler(event_type, handler)
    
    def _register_plugin_commands(self, plugin_record: PluginInstance):
        """注册插件命令"""
        commands = plugin_record.manifest.commands or {}
        
        for command_name, command_config in commands.items():
            # 这里需要集成到CLI框架中
            pass
    
    def _unregister_plugin_commands(self, plugin_record: PluginInstance):
        """注销插件命令"""
        commands = plugin_record.manifest.commands or {}
        
        for command_name in commands.keys():
            # 这里需要集成到CLI框架中
            pass
    
    def register_event_handler(self, event_type: str, handler: Callable):
        """注册事件处理器"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    def unregister_event_handler(self, event_type: str, handler: Callable):
        """注销事件处理器"""
        if event_type in self.event_handlers:
            if handler in self.event_handlers[event_type]:
                self.event_handlers[event_type].remove(handler)
    
    def emit_event(self, event_type: str, data: Dict[str, Any] = None) -> List[Any]:
        """触发事件"""
        results = []
        
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    result = handler(event_type, data or {})
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}")
        
        return results
    
    def get_plugin_info(self, plugin_name: str) -> Optional[PluginInfo]:
        """获取插件信息"""
        if plugin_name in self.plugins:
            return self.plugins[plugin_name].manifest.info
        return None
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """列出所有插件"""
        plugins = []
        
        for plugin_name, plugin_record in self.plugins.items():
            plugins.append({
                "name": plugin_name,
                "version": plugin_record.manifest.info.version,
                "description": plugin_record.manifest.info.description,
                "author": plugin_record.manifest.info.author,
                "status": plugin_record.status.value,
                "category": plugin_record.manifest.info.category,
                "loaded_at": plugin_record.loaded_at,
                "activated_at": plugin_record.activated_at
            })
        
        return plugins
    
    def get_active_plugins(self) -> List[str]:
        """获取活动插件列表"""
        return list(self.active_plugins.keys())
    
    def get_plugin_config(self, plugin_name: str) -> Dict[str, Any]:
        """获取插件配置"""
        return self.plugin_config.get(plugin_name, {})
    
    def set_plugin_config(self, plugin_name: str, config: Dict[str, Any]):
        """设置插件配置"""
        self.plugin_config[plugin_name] = config
        self.config_manager.save_plugin_config(self.plugin_config)
    
    def install_plugin(self, plugin_path: Path) -> bool:
        """安装插件"""
        try:
            # 复制插件到插件目录
            plugin_name = plugin_path.stem
            install_path = self.plugin_dir / 'third-party' / f"{plugin_name}.py"
            
            if install_path.exists():
                raise PluginLoadError(f"Plugin {plugin_name} already installed")
            
            shutil.copy2(plugin_path, install_path)
            
            # 加载插件
            loaded_name = self.load_plugin(install_path)
            if loaded_name:
                logger.info(f"Plugin installed: {plugin_name}")
                return True
            else:
                # 如果加载失败，删除文件
                install_path.unlink()
                return False
                
        except Exception as e:
            logger.error(f"Error installing plugin {plugin_path}: {e}")
            return False
    
    def uninstall_plugin(self, plugin_name: str) -> bool:
        """卸载插件"""
        try:
            # 先卸载插件
            self.unload_plugin(plugin_name)
            
            # 删除插件文件
            plugin_record = self.plugins.get(plugin_name)
            if plugin_record:
                plugin_path = self.plugin_dir / 'third-party' / f"{plugin_name}.py"
                if plugin_path.exists():
                    plugin_path.unlink()
            
            # 删除配置
            if plugin_name in self.plugin_config:
                del self.plugin_config[plugin_name]
                self.config_manager.save_plugin_config(self.plugin_config)
            
            logger.info(f"Plugin uninstalled: {plugin_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error uninstalling plugin {plugin_name}: {e}")
            return False
```

## 插件开发规范

### 1. 插件开发模板

```python
# plugins/example_plugin.py
"""
示例插件 - 展示插件开发的基本结构
"""
from dwrg_manager.plugins.base import PluginInterface, PluginInfo
from dwrg_manager.utils.logger import logger

class ExamplePlugin(PluginInterface):
    """示例插件"""
    
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="example",
            version="1.0.0",
            description="这是一个示例插件",
            author="Example Author",
            email="author@example.com",
            website="https://example.com",
            license="MIT",
            dependencies=[],
            min_app_version="1.0.0",
            max_app_version="2.0.0",
            tags=["example", "demo"],
            category="utility",
            icon="🔧"
        )
    
    def get_permissions(self) -> list:
        """获取插件所需的权限"""
        return [
            "read_config",
            "write_config",
            "read_files",
            "write_files"
        ]
    
    def get_resources(self) -> list:
        """获取插件所需的资源"""
        return [
            "config/example.json",
            "templates/example.html"
        ]
    
    def get_hooks(self) -> dict:
        """获取插件注册的钩子"""
        return {
            "before_command": ["handle_before_command"],
            "after_command": ["handle_after_command"],
            "on_error": ["handle_error"]
        }
    
    def get_commands(self) -> dict:
        """获取插件注册的命令"""
        return {
            "example": {
                "name": "示例命令",
                "description": "这是一个示例命令",
                "usage": "dwrg example [options]",
                "options": [
                    {
                        "name": "--option",
                        "description": "示例选项",
                        "required": False,
                        "default": None
                    }
                ]
            }
        }
    
    def on_load(self) -> bool:
        """插件加载时调用"""
        self.log("info", "示例插件加载成功")
        return True
    
    def on_activate(self) -> bool:
        """插件激活时调用"""
        self.log("info", "示例插件激活成功")
        return True
    
    def on_deactivate(self) -> bool:
        """插件停用时调用"""
        self.log("info", "示例插件停用成功")
        return True
    
    def on_unload(self) -> bool:
        """插件卸载时调用"""
        self.log("info", "示例插件卸载成功")
        return True
    
    def handle_command(self, command: str, args: dict) -> dict:
        """处理命令"""
        if command == "example":
            return self.handle_example_command(args)
        return {"success": False, "error": "Unknown command"}
    
    def handle_example_command(self, args: dict) -> dict:
        """处理示例命令"""
        option = args.get("option", "default")
        
        self.log("info", f"执行示例命令，选项: {option}")
        
        return {
            "success": True,
            "message": f"示例命令执行成功，选项: {option}",
            "data": {
                "option": option,
                "timestamp": time.time()
            }
        }
    
    def handle_before_command(self, event_type: str, data: dict) -> dict:
        """处理命令前钩子"""
        self.log("info", f"命令执行前: {data.get('command', 'unknown')}")
        return {"proceed": True}
    
    def handle_after_command(self, event_type: str, data: dict) -> dict:
        """处理命令后钩子"""
        self.log("info", f"命令执行后: {data.get('command', 'unknown')}")
        return {"success": data.get('success', False)}
    
    def handle_error(self, event_type: str, data: dict) -> dict:
        """处理错误钩子"""
        self.log("error", f"错误发生: {data.get('error', 'unknown')}")
        return {"handled": True}
```

### 2. 插件清单文件

```json
// plugin.json
{
  "info": {
    "name": "example",
    "version": "1.0.0",
    "description": "这是一个示例插件",
    "author": "Example Author",
    "email": "author@example.com",
    "website": "https://example.com",
    "license": "MIT",
    "dependencies": [],
    "minAppVersion": "1.0.0",
    "maxAppVersion": "2.0.0",
    "tags": ["example", "demo"],
    "category": "utility",
    "icon": "🔧"
  },
  "entryPoint": "ExamplePlugin",
  "configSchema": {
    "type": "object",
    "properties": {
      "enabled": {
        "type": "boolean",
        "default": true,
        "description": "是否启用插件"
      },
      "option1": {
        "type": "string",
        "default": "default_value",
        "description": "选项1"
      },
      "option2": {
        "type": "number",
        "default": 42,
        "description": "选项2"
      }
    }
  },
  "permissions": [
    "read_config",
    "write_config",
    "read_files",
    "write_files"
  ],
  "resources": [
    "config/example.json",
    "templates/example.html"
  ],
  "hooks": {
    "before_command": ["handle_before_command"],
    "after_command": ["handle_after_command"],
    "on_error": ["handle_error"]
  },
  "commands": {
    "example": {
      "name": "示例命令",
      "description": "这是一个示例命令",
      "usage": "dwrg example [options]",
      "options": [
        {
          "name": "--option",
          "description": "示例选项",
          "required": false,
          "default": null
        }
      ]
    }
  }
}
```

### 3. 插件配置规范

```python
# src/dwrg_manager/plugins/config.py
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import json

@dataclass
class PluginConfig:
    """插件配置"""
    enabled: bool = True
    auto_load: bool = False
    config: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.config is None:
            self.config = {}

class PluginConfigManager:
    """插件配置管理器"""
    
    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.config_file = config_dir / "plugins.json"
        self.plugin_configs: Dict[str, PluginConfig] = {}
        
        # 加载配置
        self._load_config()
    
    def _load_config(self):
        """加载配置"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for plugin_name, plugin_data in data.items():
                        self.plugin_configs[plugin_name] = PluginConfig(**plugin_data)
            except Exception as e:
                print(f"Error loading plugin config: {e}")
    
    def _save_config(self):
        """保存配置"""
        try:
            data = {}
            for plugin_name, plugin_config in self.plugin_configs.items():
                data[plugin_name] = asdict(plugin_config)
            
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving plugin config: {e}")
    
    def get_plugin_config(self, plugin_name: str) -> PluginConfig:
        """获取插件配置"""
        if plugin_name not in self.plugin_configs:
            self.plugin_configs[plugin_name] = PluginConfig()
        return self.plugin_configs[plugin_name]
    
    def set_plugin_config(self, plugin_name: str, config: PluginConfig):
        """设置插件配置"""
        self.plugin_configs[plugin_name] = config
        self._save_config()
    
    def get_enabled_plugins(self) -> List[str]:
        """获取启用的插件列表"""
        return [
            plugin_name 
            for plugin_name, config in self.plugin_configs.items() 
            if config.enabled
        ]
    
    def enable_plugin(self, plugin_name: str):
        """启用插件"""
        if plugin_name not in self.plugin_configs:
            self.plugin_configs[plugin_name] = PluginConfig()
        self.plugin_configs[plugin_name].enabled = True
        self._save_config()
    
    def disable_plugin(self, plugin_name: str):
        """禁用插件"""
        if plugin_name in self.plugin_configs:
            self.plugin_configs[plugin_name].enabled = False
            self._save_config()
    
    def set_plugin_auto_load(self, plugin_name: str, auto_load: bool):
        """设置插件自动加载"""
        if plugin_name not in self.plugin_configs:
            self.plugin_configs[plugin_name] = PluginConfig()
        self.plugin_configs[plugin_name].auto_load = auto_load
        self._save_config()
    
    def get_plugin_auto_load(self, plugin_name: str) -> bool:
        """获取插件自动加载设置"""
        if plugin_name not in self.plugin_configs:
            return False
        return self.plugin_configs[plugin_name].auto_load
    
    def update_plugin_config(self, plugin_name: str, config: Dict[str, Any]):
        """更新插件配置"""
        if plugin_name not in self.plugin_configs:
            self.plugin_configs[plugin_name] = PluginConfig()
        
        self.plugin_configs[plugin_name].config.update(config)
        self._save_config()
    
    def get_plugin_config_data(self, plugin_name: str) -> Dict[str, Any]:
        """获取插件配置数据"""
        if plugin_name not in self.plugin_configs:
            return {}
        return self.plugin_configs[plugin_name].config
    
    def reset_plugin_config(self, plugin_name: str):
        """重置插件配置"""
        if plugin_name in self.plugin_configs:
            self.plugin_configs[plugin_name] = PluginConfig()
            self._save_config()
```

## 插件测试规范

### 1. 插件测试框架

```python
# tests/plugins/test_plugin_manager.py
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from dwrg_manager.plugins.manager import PluginManager, PluginLoadError
from dwrg_manager.plugins.base import PluginInterface, PluginInfo

class MockPlugin(PluginInterface):
    """模拟插件"""
    
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="mock",
            version="1.0.0",
            description="Mock plugin",
            author="Test Author"
        )

class TestPluginManager:
    """插件管理器测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.plugin_dir = self.temp_dir / "plugins"
        self.plugin_dir.mkdir()
        
        # 创建模拟配置管理器
        self.config_manager = Mock()
        self.config_manager.get_plugin_config.return_value = {}
        
        # 创建插件管理器
        self.plugin_manager = PluginManager(self.config_manager, self.plugin_dir)
    
    def test_load_plugin(self):
        """测试插件加载"""
        # 创建模拟插件文件
        plugin_file = self.plugin_dir / "mock_plugin.py"
        plugin_code = '''
from tests.plugins.test_plugin_manager import MockPlugin

class TestPlugin(MockPlugin):
    def on_load(self):
        return True
'''
        with open(plugin_file, 'w', encoding='utf-8') as f:
            f.write(plugin_code)
        
        # 加载插件
        plugin_name = self.plugin_manager.load_plugin(plugin_file)
        
        assert plugin_name == "mock"
        assert plugin_name in self.plugin_manager.plugins
        assert plugin_name in self.plugin_manager.loaded_plugins
    
    def test_load_invalid_plugin(self):
        """测试加载无效插件"""
        # 创建无效插件文件
        plugin_file = self.plugin_dir / "invalid_plugin.py"
        plugin_code = '''
# 无效的插件文件
def some_function():
    pass
'''
        with open(plugin_file, 'w', encoding='utf-8') as f:
            f.write(plugin_code)
        
        # 尝试加载插件
        with pytest.raises(PluginLoadError):
            self.plugin_manager.load_plugin(plugin_file)
    
    def test_activate_plugin(self):
        """测试激活插件"""
        # 先加载插件
        plugin_file = self.plugin_dir / "mock_plugin.py"
        plugin_code = '''
from tests.plugins.test_plugin_manager import MockPlugin

class TestPlugin(MockPlugin):
    def on_load(self):
        return True
    def on_activate(self):
        return True
'''
        with open(plugin_file, 'w', encoding='utf-8') as f:
            f.write(plugin_code)
        
        plugin_name = self.plugin_manager.load_plugin(plugin_file)
        
        # 激活插件
        result = self.plugin_manager.activate_plugin(plugin_name)
        
        assert result is True
        assert plugin_name in self.plugin_manager.active_plugins
    
    def test_deactivate_plugin(self):
        """测试停用插件"""
        # 先加载并激活插件
        plugin_file = self.plugin_dir / "mock_plugin.py"
        plugin_code = '''
from tests.plugins.test_plugin_manager import MockPlugin

class TestPlugin(MockPlugin):
    def on_load(self):
        return True
    def on_activate(self):
        return True
    def on_deactivate(self):
        return True
'''
        with open(plugin_file, 'w', encoding='utf-8') as f:
            f.write(plugin_code)
        
        plugin_name = self.plugin_manager.load_plugin(plugin_file)
        self.plugin_manager.activate_plugin(plugin_name)
        
        # 停用插件
        result = self.plugin_manager.deactivate_plugin(plugin_name)
        
        assert result is True
        assert plugin_name not in self.plugin_manager.active_plugins
    
    def test_unload_plugin(self):
        """测试卸载插件"""
        # 先加载插件
        plugin_file = self.plugin_dir / "mock_plugin.py"
        plugin_code = '''
from tests.plugins.test_plugin_manager import MockPlugin

class TestPlugin(MockPlugin):
    def on_load(self):
        return True
    def on_unload(self):
        return True
'''
        with open(plugin_file, 'w', encoding='utf-8') as f:
            f.write(plugin_code)
        
        plugin_name = self.plugin_manager.load_plugin(plugin_file)
        
        # 卸载插件
        result = self.plugin_manager.unload_plugin(plugin_name)
        
        assert result is True
        assert plugin_name not in self.plugin_manager.loaded_plugins
        assert plugin_name not in self.plugin_manager.plugins
    
    def test_list_plugins(self):
        """测试列出插件"""
        # 加载插件
        plugin_file = self.plugin_dir / "mock_plugin.py"
        plugin_code = '''
from tests.plugins.test_plugin_manager import MockPlugin

class TestPlugin(MockPlugin):
    def on_load(self):
        return True
'''
        with open(plugin_file, 'w', encoding='utf-8') as f:
            f.write(plugin_code)
        
        self.plugin_manager.load_plugin(plugin_file)
        
        # 列出插件
        plugins = self.plugin_manager.list_plugins()
        
        assert len(plugins) == 1
        assert plugins[0]["name"] == "mock"
        assert plugins[0]["version"] == "1.0.0"
    
    def test_get_plugin_info(self):
        """测试获取插件信息"""
        # 加载插件
        plugin_file = self.plugin_dir / "mock_plugin.py"
        plugin_code = '''
from tests.plugins.test_plugin_manager import MockPlugin

class TestPlugin(MockPlugin):
    def on_load(self):
        return True
'''
        with open(plugin_file, 'w', encoding='utf-8') as f:
            f.write(plugin_code)
        
        plugin_name = self.plugin_manager.load_plugin(plugin_file)
        
        # 获取插件信息
        info = self.plugin_manager.get_plugin_info(plugin_name)
        
        assert info is not None
        assert info.name == "mock"
        assert info.version == "1.0.0"
    
    def test_event_system(self):
        """测试事件系统"""
        # 注册事件处理器
        def event_handler(event_type, data):
            return {"handled": True, "event": event_type}
        
        self.plugin_manager.register_event_handler("test_event", event_handler)
        
        # 触发事件
        results = self.plugin_manager.emit_event("test_event", {"data": "test"})
        
        assert len(results) == 1
        assert results[0]["handled"] is True
        assert results[0]["event"] == "test_event"
```

### 2. 插件单元测试

```python
# tests/plugins/test_plugin_interface.py
import pytest
from unittest.mock import Mock

from dwrg_manager.plugins.base import PluginInterface, PluginInfo

class TestPluginInterface:
    """插件接口测试"""
    
    def test_plugin_info_property(self):
        """测试插件信息属性"""
        class TestPlugin(PluginInterface):
            @property
            def info(self) -> PluginInfo:
                return PluginInfo(
                    name="test",
                    version="1.0.0",
                    description="Test plugin",
                    author="Test Author"
                )
        
        plugin = TestPlugin(None)
        info = plugin.info
        
        assert info.name == "test"
        assert info.version == "1.0.0"
        assert info.description == "Test plugin"
        assert info.author == "Test Author"
    
    def test_plugin_lifecycle(self):
        """测试插件生命周期"""
        class TestPlugin(PluginInterface):
            def __init__(self, plugin_manager):
                super().__init__(plugin_manager)
                self.load_called = False
                self.activate_called = False
                self.deactivate_called = False
                self.unload_called = False
            
            @property
            def info(self) -> PluginInfo:
                return PluginInfo(
                    name="test",
                    version="1.0.0",
                    description="Test plugin",
                    author="Test Author"
                )
            
            def on_load(self):
                self.load_called = True
                return True
            
            def on_activate(self):
                self.activate_called = True
                return True
            
            def on_deactivate(self):
                self.deactivate_called = True
                return True
            
            def on_unload(self):
                self.unload_called = True
                return True
        
        # 创建插件
        plugin_manager = Mock()
        plugin = TestPlugin(plugin_manager)
        
        # 测试加载
        assert plugin.on_load() is True
        assert plugin.load_called is True
        
        # 测试激活
        assert plugin.on_activate() is True
        assert plugin.activate_called is True
        
        # 测试停用
        assert plugin.on_deactivate() is True
        assert plugin.deactivate_called is True
        
        # 测试卸载
        assert plugin.on_unload() is True
        assert plugin.unload_called is True
    
    def test_plugin_logging(self):
        """测试插件日志"""
        class TestPlugin(PluginInterface):
            @property
            def info(self) -> PluginInfo:
                return PluginInfo(
                    name="test",
                    version="1.0.0",
                    description="Test plugin",
                    author="Test Author"
                )
        
        # 创建插件
        plugin_manager = Mock()
        plugin = TestPlugin(plugin_manager)
        
        # 创建模拟日志器
        logger = Mock()
        plugin.set_logger(logger)
        
        # 测试日志记录
        plugin.log("info", "Test message", key="value")
        
        # 验证日志调用
        logger.info.assert_called_once_with("Test message", key="value")
```

## 插件发布规范

### 1. 插件打包脚本

```bash
#!/bin/bash

# 插件打包脚本
set -e

# 配置
PLUGIN_NAME=$1
PLUGIN_VERSION=$2
PLUGIN_DIR="plugins/${PLUGIN_NAME}"
OUTPUT_DIR="dist/plugins"
PACKAGE_NAME="${PLUGIN_NAME}-${PLUGIN_VERSION}"

if [ -z "$PLUGIN_NAME" ] || [ -z "$PLUGIN_VERSION" ]; then
    echo "使用方法: $0 <插件名称> <版本号>"
    exit 1
fi

# 创建输出目录
mkdir -p "${OUTPUT_DIR}"

echo "开始打包插件: ${PLUGIN_NAME} v${PLUGIN_VERSION}"

# 检查插件目录
if [ ! -d "${PLUGIN_DIR}" ]; then
    echo "错误: 插件目录不存在: ${PLUGIN_DIR}"
    exit 1
fi

# 创建临时目录
TEMP_DIR=$(mktemp -d)
PACKAGE_DIR="${TEMP_DIR}/${PACKAGE_NAME}"

# 复制插件文件
echo "复制插件文件..."
mkdir -p "${PACKAGE_DIR}"
cp -r "${PLUGIN_DIR}"/* "${PACKAGE_DIR}/"

# 创建插件清单
echo "创建插件清单..."
cat > "${PACKAGE_DIR}/plugin.json" << EOF
{
  "info": {
    "name": "${PLUGIN_NAME}",
    "version": "${PLUGIN_VERSION}",
    "description": "$(jq -r '.info.description' "${PACKAGE_DIR}/plugin.json" 2>/dev/null || echo "插件描述")",
    "author": "$(jq -r '.info.author' "${PACKAGE_DIR}/plugin.json" 2>/dev/null || echo "作者")",
    "email": "$(jq -r '.info.email' "${PACKAGE_DIR}/plugin.json" 2>/dev/null || echo "")",
    "website": "$(jq -r '.info.website' "${PACKAGE_DIR}/plugin.json" 2>/dev/null || echo "")",
    "license": "$(jq -r '.info.license' "${PACKAGE_DIR}/plugin.json" 2>/dev/null || echo "MIT")",
    "dependencies": $(jq -r '.info.dependencies // []' "${PACKAGE_DIR}/plugin.json" 2>/dev/null || echo "[]"),
    "minAppVersion": "$(jq -r '.info.minAppVersion // "1.0.0"' "${PACKAGE_DIR}/plugin.json" 2>/dev/null || echo "1.0.0")",
    "maxAppVersion": "$(jq -r '.info.maxAppVersion // "2.0.0"' "${PACKAGE_DIR}/plugin.json" 2>/dev/null || echo "2.0.0")",
    "tags": $(jq -r '.info.tags // []' "${PACKAGE_DIR}/plugin.json" 2>/dev/null || echo "[]"),
    "category": "$(jq -r '.info.category // "general"' "${PACKAGE_DIR}/plugin.json" 2>/dev/null || echo "general")",
    "icon": "$(jq -r '.info.icon // ""' "${PACKAGE_DIR}/plugin.json" 2>/dev/null || echo "")"
  },
  "entryPoint": "$(jq -r '.entryPoint // ""' "${PACKAGE_DIR}/plugin.json" 2>/dev/null || echo "")",
  "configSchema": $(jq -r '.configSchema // {}' "${PACKAGE_DIR}/plugin.json" 2>/dev/null || echo "{}"),
  "permissions": $(jq -r '.permissions // []' "${PACKAGE_DIR}/plugin.json" 2>/dev/null || echo "[]"),
  "resources": $(jq -r '.resources // []' "${PACKAGE_DIR}/plugin.json" 2>/dev/null || echo "[]"),
  "hooks": $(jq -r '.hooks // {}' "${PACKAGE_DIR}/plugin.json" 2>/dev/null || echo "{}"),
  "commands": $(jq -r '.commands // {}' "${PACKAGE_DIR}/plugin.json" 2>/dev/null || echo "{}")
}
EOF

# 创建安装脚本
cat > "${PACKAGE_DIR}/install.sh" << 'EOF'
#!/bin/bash

# 插件安装脚本
set -e

echo "开始安装插件..."

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_NAME="$(basename "$SCRIPT_DIR")"

# 检查插件管理器
if ! command -v dwrg &> /dev/null; then
    echo "错误: 未找到 dwrg 命令"
    exit 1
fi

# 安装插件
echo "安装插件: ${PLUGIN_NAME}"
dwrg plugin install "${SCRIPT_DIR}"

echo "插件安装完成"
EOF

# 创建卸载脚本
cat > "${PACKAGE_DIR}/uninstall.sh" << 'EOF'
#!/bin/bash

# 插件卸载脚本
set -e

echo "开始卸载插件..."

# 获取插件名称
PLUGIN_NAME="$(basename "$(dirname "$0")")"

# 检查插件管理器
if ! command -v dwrg &> /dev/null; then
    echo "错误: 未找到 dwrg 命令"
    exit 1
fi

# 卸载插件
echo "卸载插件: ${PLUGIN_NAME}"
dwrg plugin uninstall "${PLUGIN_NAME}"

echo "插件卸载完成"
EOF

# 设置执行权限
chmod +x "${PACKAGE_DIR}/install.sh"
chmod +x "${PACKAGE_DIR}/uninstall.sh"

# 创建压缩包
echo "创建压缩包..."
cd "${TEMP_DIR}"
tar -czf "${OUTPUT_DIR}/${PACKAGE_NAME}.tar.gz" "${PACKAGE_NAME}"

# 创建ZIP包
zip -r "${OUTPUT_DIR}/${PACKAGE_NAME}.zip" "${PACKAGE_NAME}"

# 清理临时目录
rm -rf "${TEMP_DIR}"

echo "插件打包完成:"
echo "  - ${OUTPUT_DIR}/${PACKAGE_NAME}.tar.gz"
echo "  - ${OUTPUT_DIR}/${PACKAGE_NAME}.zip"
```

### 2. 插件发布检查清单

```bash
#!/bin/bash

# 插件发布检查脚本
echo "插件发布检查开始..."

# 检查清单
checklist=(
    "插件名称和版本"
    "插件信息完整性"
    "依赖关系检查"
    "权限检查"
    "资源文件检查"
    "代码质量检查"
    "测试覆盖率"
    "文档完整性"
    "安装脚本"
    "卸载脚本"
)

# 检查插件信息
echo "检查插件信息..."
if [ ! -f "plugin.json" ]; then
    echo "❌ 错误: 缺少 plugin.json 文件"
    exit 1
fi

# 检查必需字段
required_fields=("name" "version" "description" "author")
for field in "${required_fields[@]}"; do
    if ! jq -e ".info.${field}" plugin.json >/dev/null 2>&1; then
        echo "❌ 错误: 缺少必需字段: ${field}"
        exit 1
    fi
done

# 检查依赖关系
echo "检查依赖关系..."
dependencies=$(jq -r '.info.dependencies // []' plugin.json)
if [ "$dependencies" != "[]" ]; then
    echo "⚠️  警告: 插件有依赖关系"
    echo "   依赖: $dependencies"
fi

# 检查权限
echo "检查权限..."
permissions=$(jq -r '.permissions // []' plugin.json)
if [ "$permissions" != "[]" ]; then
    echo "⚠️  警告: 插件请求特殊权限"
    echo "   权限: $permissions"
fi

# 检查资源文件
echo "检查资源文件..."
resources=$(jq -r '.resources // []' plugin.json)
if [ "$resources" != "[]" ]; then
    for resource in $(echo "$resources" | jq -r '.[]'); do
        if [ ! -f "$resource" ]; then
            echo "❌ 错误: 缺少资源文件: $resource"
            exit 1
        fi
    done
fi

# 检查Python语法
echo "检查Python语法..."
for py_file in *.py; do
    if [ -f "$py_file" ]; then
        if ! python -m py_compile "$py_file"; then
            echo "❌ 错误: Python语法错误: $py_file"
            exit 1
        fi
    fi
done

# 检查测试文件
echo "检查测试文件..."
if [ ! -d "tests" ]; then
    echo "⚠️  警告: 缺少测试目录"
else
    test_count=$(find tests -name "*.py" | wc -l)
    echo "✅ 找到 $test_count 个测试文件"
fi

# 检查文档
echo "检查文档..."
if [ ! -f "README.md" ]; then
    echo "⚠️  警告: 缺少 README.md"
fi

# 检查安装和卸载脚本
echo "检查安装脚本..."
if [ ! -f "install.sh" ]; then
    echo "❌ 错误: 缺少 install.sh"
    exit 1
fi

if [ ! -f "uninstall.sh" ]; then
    echo "❌ 错误: 缺少 uninstall.sh"
    exit 1
fi

# 检查脚本执行权限
if [ ! -x "install.sh" ] || [ ! -x "uninstall.sh" ]; then
    echo "❌ 错误: 安装/卸载脚本没有执行权限"
    exit 1
fi

echo "✅ 所有检查通过"
echo "插件可以发布"
```

这个插件系统标准文档提供了完整的插件开发、管理和发布指南，确保项目具有良好的扩展性和可维护性。