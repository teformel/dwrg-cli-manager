---
name: project-plan-dwrg-cli-manager
description: 第五人格命令行管理器项目计划，多渠道服和多账号管理工具
metadata:
  node_type: memory
  type: project
  created_date: 2026-09-21
  status: planning
  originSessionId: sess_30048853-8656-4451-96f5-dd221dfd42ae
---

# 第五人格命令行管理器项目计划

## 项目概述
开发一款类似 wutheringwaves-cli-manager 的第五人格游戏命令行管理器，专门用于管理第五人格多渠道服和多账号。项目将一次性完整实现所有功能，提供类似 `ww` 命令的 `dwrg` CLI工具，支持版本检查、账号管理、渠道服切换、资源管理和游戏启动等完整功能。

## 核心功能需求

### 1. 多渠道服管理
- 支持多个游戏渠道服（官方服、B服、官服等）
- 快速切换不同渠道服
- 自动检测和修复渠道服差异
- 渠道服配置管理

### 2. 多账号管理
- 支持多个游戏账号管理
- 账号信息加密存储
- 快速切换登录账号
- 账号状态监控

### 3. 游戏资源管理
- 全量游戏文件下载
- 增量更新机制
- MD5校验确保文件完整性
- 本地缓存加速

### 4. 启动管理
- 支持不同渠道服独立启动
- 自动配置启动参数
- 支持启动前检查
- 错误诊断和修复

## 技术栈选择

### 核心技术
- **语言**: Python 3.10+
- **CLI框架**: Typer（现代化、类型安全的CLI框架）
- **包管理**: uv（现代Python包管理器）
- **异步处理**: asyncio + aiohttp（网络请求）
- **并发下载**: asyncio + aiofiles（文件操作）

### 辅助工具
- **配置管理**: pydantic（数据验证）
- **加密**: cryptography（账号信息加密）
- **日志**: loguru（结构化日志）
- **进度条**: tqdm（下载进度显示）

## 项目结构设计

```
dwrg-cli-manager/
├── src/
│   └── dwrg_manager/
│       ├── __init__.py
│       ├── main.py              # CLI入口点
│       ├── config/               # 配置管理
│       │   ├── __init__.py
│       │   ├── models.py         # 配置数据模型
│       │   └── manager.py        # 配置管理器
│       ├── accounts/             # 账号管理
│       │   ├── __init__.py
│       │   ├── models.py         # 账号数据模型
│       │   ├── storage.py        # 账号存储
│       │   └── manager.py        # 账号管理器
│       ├── servers/              # 渠道服管理
│       │   ├── __init__.py
│       │   ├── models.py         # 渠道服数据模型
│       │   ├── detection.py      # 渠道服检测
│       │   └── manager.py        # 渠道服管理器
│       ├── resources/            # 资源管理
│       │   ├── __init__.py
│       │   ├── downloader.py     # 下载器
│       │   ├── patcher.py       # 补丁管理
│       │   └── validator.py      # 文件验证
│       ├── launcher/             # 启动管理
│       │   ├── __init__.py
│       │   ├── models.py         # 启动配置模型
│       │   └── manager.py        # 启动管理器
│       └── utils/               # 工具函数
│           ├── __init__.py
│           ├── crypto.py         # 加密工具
│           ├── logger.py         # 日志工具
│           └── system.py         # 系统工具
├── scripts/                     # 辅助脚本
├── tests/                       # 测试文件
├── docs/                        # 文档
├── pyproject.toml              # 项目配置
├── README.md                   # 项目说明
└── requirements.txt           # 依赖文件
```

## 开发阶段规划

### 阶段1：项目初始化（1天）
- 项目目录结构创建
- pyproject.toml配置
- 基础依赖安装
- 开发环境配置

### 阶段2：核心框架搭建（2-3天）
- CLI命令框架实现（dwrg命令）
- 配置管理系统
- 日志系统
- 错误处理机制

### 阶段3：账号管理系统（3-4天）
- 账号数据模型
- 加密存储功能
- 账号管理CLI命令
- 状态监控功能

### 阶段4：渠道服管理（3-4天）
- 渠道服数据模型
- 检测和识别功能
- 切换功能实现
- 配置管理

### 阶段5：资源管理（4-5天）
- 下载器实现
- 增量更新机制
- 文件验证系统
- 缓存管理

### 阶段6：启动管理（2-3天）
- 启动配置管理
- 参数处理
- 错误诊断
- 启动前检查

### 阶段7：测试和优化（2-3天）
- 单元测试
- 集成测试
- 性能优化
- 文档完善

## 关键技术实现点

### 1. CLI命令系统
- **主命令**: `dwrg` - 类似 `ww` 的简洁命令行工具
- **子命令**: 完整的子命令系统，支持账号、服务器、资源、启动等管理
- **参数解析**: 使用 Typer 实现强大的参数解析和验证
- **自动补全**: 支持 shell 自动补全功能
- **版本管理**: 内置版本检查和更新机制

### 2. 多渠道服切换机制
- **智能检测**: 自动检测当前渠道服类型
- **文件差异**: 基于MD5的文件差异检测算法
- **无缝切换**: 快速切换渠道服，无需重新下载
- **自动备份**: 切换前自动备份，支持回滚
- **配置管理**: 统一的渠道服配置文件管理

### 3. 多账号安全存储
- **AES-256**: 使用业界标准加密算法
- **密钥管理**: 安全的密钥生成和存储机制
- **密码安全**: 安全的密码管理和自动填充
- **状态监控**: 实时账号状态和登录信息
- **批量操作**: 支持批量账号管理操作

### 4. 增量更新系统
- **差异检测**: 基于MD5和文件大小的智能差异检测
- **断点续传**: 网络中断后自动断点续传
- **并发下载**: 多线程并发下载，支持速度限制
- **缓存管理**: 智能缓存管理，节省磁盘空间
- **完整性校验**: 下载完成后自动完整性校验

### 5. 错误处理和诊断
- **分级错误**: 错误分级处理，用户友好的错误信息
- **自动诊断**: 自动检测和诊断常见问题
- **修复建议**: 提供具体的修复建议和操作
- **日志系统**: 完整的操作日志和错误日志
- **远程诊断**: 支持远程诊断和问题上报

## CLI命令设计

参考 wutheringwaves-cli-manager 的 `ww` 命令，我们将实现 `dwrg` 命令行工具：

### 基础命令
```bash
# 显示版本信息
dwrg --version
dwrg -v

# 显示帮助信息
dwrg --help
dwrg -h

# 显示详细帮助
dwrg help <command>
```

### 账号管理命令
```bash
# 添加账号
dwrg account add --username <用户名> --server <渠道服> --password <密码>

# 列出所有账号
dwrg account list [--server <渠道服>]

# 切换当前账号
dwrg account switch <账号ID>

# 删除账号
dwrg account remove <账号ID>

# 账号状态
dwrg account status <账号ID>
```

### 渠道服管理命令
```bash
# 列出所有渠道服
dwrg server list

# 检测当前渠道服
dwrg server detect

# 切换渠道服
dwrg server switch <渠道服名称>

# 渠道服信息
dwrg server info <渠道服名称>
```

### 资源管理命令
```bash
# 检查游戏文件完整性
dwrg resource check

# 下载/更新游戏文件
dwrg resource update [--server <渠道服>]

# 清理缓存
dwrg resource clean

# 显示缓存信息
dwrg resource info
```

### 启动管理命令
```bash
# 启动游戏
dwrg launch [--account <账号ID>] [--server <渠道服>]

# 启动诊断
dwrg diagnose

# 配置启动参数
dwrg config launch [--param <参数>] [--value <值>]
```

### 配置管理命令
```bash
# 显示配置
dwrg config show

# 设置配置
dwrg config set <key> <value>

# 重置配置
dwrg config reset

# 导出配置
dwrg config export <文件路径>

# 导入配置
dwrg config import <文件路径>
```

## 发布计划

### v1.0.0 完整版本（一次性发布）
- 所有核心功能一次性实现
- 完整的CLI命令支持
- 完善的错误处理和诊断
- 高性能的异步处理
- 完整的文档和测试

### 即时更新策略
- 使用 `dwrg self-update` 命令进行自动更新
- 增量更新机制确保快速部署
- 版本兼容性保证

## 维护和更新
- **自动更新**: `dwrg self-update` 命令实现一键更新
- **版本兼容性**: 自动检测和适配游戏版本更新
- **性能优化**: 持续的性能监控和优化
- **用户反馈**: 内置反馈收集机制
- **快速响应**: 游戏更新后24小时内提供兼容性补丁