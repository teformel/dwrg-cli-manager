---
name: cli-command-design-dwrg
description: 第五人格命令行管理器的CLI命令设计优化
metadata:
  node_type: memory
  type: project
  created_date: 2026-09-21
  status: active
  originSessionId: sess_30048853-8656-4451-96f5-dd221dfd42ae
---

# CLI命令设计优化 - 第五人格命令行管理器

## 设计理念

基于用户友好性和命令简洁性原则，优化CLI命令设计，避免冗余参数，提高用户体验。

## 命令设计原则

1. **上下文感知**: 子命令已经明确了操作对象，不需要重复参数
2. **简洁性**: 减少不必要的参数，提高命令可读性
3. **一致性**: 相似操作使用相似的命令结构
4. **可扩展性**: 预留未来扩展空间

## 优化后的命令设计

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
dwrg account add --username <用户名> --password <密码> [--server <渠道服>]

# 列出所有账号
dwrg account list

# 列出特定服务器的账号
dwrg account list --server official

# 切换当前账号
dwrg account switch <账号ID>

# 删除账号
dwrg account remove <账号ID>

# 账号状态
dwrg account status <账号ID>

# 账号登录
dwrg account login <账号ID>
```

### 渠道服管理命令 ⭐ 优化
```bash
# 列出所有渠道服
dwrg server list

# 检测当前渠道服
dwrg server detect

# 切换渠道服
dwrg server switch official

# 切换到B服
dwrg server switch bserver

# 强制切换（跳过确认）
dwrg server switch bserver --force

# 查看渠道服信息
dwrg server info official

# 查看B服信息
dwrg server info bserver
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
dwrg config set launch.param <value>
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

## 命令设计对比

### 优化前（冗余）
```bash
# 冗余的--server参数
dwrg server switch --server official
dwrg server switch --server bserver
dwrg server info --server official
```

### 优化后（简洁）
```bash
# 直接使用服务器名称
dwrg server switch official
dwrg server switch bserver
dwrg server info official
```

## 设计优势

### 1. 减少冗余
- 子命令已经明确了操作对象（server）
- 不需要重复指定 --server 参数
- 命令更加简洁易读

### 2. 提高效率
- 减少键盘输入
- 降低记忆负担
- 提高命令执行速度

### 3. 增强可读性
- 命令结构更清晰
- 更容易理解命令意图
- 减少视觉噪音

### 4. 保持一致性
- 所有子命令都遵循相同模式
- 用户学习成本降低
- 便于批量操作

## 特殊情况处理

### 1. 多参数情况
```bash
# 当需要多个参数时，使用参数名
dwrg account add --username user1 --password pass123 --server official
```

### 2. 可选参数
```bash
# 可选参数仍然使用参数名
dwrg resource update --server official
dwrg launch --account acc123
```

### 3. 冲突解决
```bash
# 如果服务器名称与子命令冲突，使用参数名
dwrg server switch --help  # 查看帮助，而不是切换help服务器
```

## 用户反馈机制

### 1. 自动补全
```bash
# 支持tab补全
dwrg server switch <tab>  # 显示所有可用服务器
dwrg account switch <tab>  # 显示所有可用账号
```

### 2. 命令建议
```bash
# 当用户输入错误时，提供建议
dwrg server swich official  # 自动纠正为 switch
dwrg account swtich acc123  # 自动纠正为 switch
```

### 3. 交互式确认
```bash
# 对于重要操作，提供确认提示
$ dwrg server switch bserver
即将切换到B服，当前游戏进程将被终止。是否继续？(y/N): y
```

## 实现建议

### 1. 参数解析
```python
# 使用 Typer 的参数解析
@app.command()
def switch(server: str = typer.Argument(..., help="目标服务器名称")):
    """切换渠道服"""
    pass
```

### 2. 验证机制
```python
# 验证服务器名称
valid_servers = ["official", "bserver", "test_server"]

if server not in valid_servers:
    typer.echo(f"错误：无效的服务器名称 {server}")
    typer.echo(f"可用服务器：{', '.join(valid_servers)}")
    raise typer.Exit(1)
```

### 3. 帮助系统
```python
# 提供详细的帮助信息
@app.command()
def switch(server: str):
    """切换渠道服
    
    支持的服务器：
    - official: 官方服
    - bserver: B服
    - test_server: 测试服
    
    示例：
    dwrg server switch official
    dwrg server switch bserver --force
    """
    pass
```

## 总结

优化后的命令设计更加简洁、直观，减少了冗余参数，提高了用户体验。通过上下文感知的设计，让用户能够更自然地使用命令，同时保持了系统的可扩展性和一致性。