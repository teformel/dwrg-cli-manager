---
name: linux-cli-standards-dwrg
description: 第五人格命令行管理器的Linux命令规范设计
metadata:
  node_type: memory
  type: project
  created_date: 2026-09-21
  status: active
  originSessionId: sess_30048853-8656-4451-96f5-dd221dfd42ae
---

# Linux命令规范设计 - 第五人格命令行管理器

## 设计理念

严格遵循Linux命令规范和用户习惯，设计符合行业标准的CLI工具，确保命令的一致性、可预测性和易用性。

## Linux命令设计原则

### 1. 命令命名规范
- 使用小写字母和连字符（-）
- 避免缩写，使用完整单词
- 保持命令名称简洁明了
- 遵循POSIX标准

### 2. 参数设计规范
- 长选项使用双连字符（--）
- 短选项使用单连字符（-）
- 布尔参数使用标志形式
- 必需参数位置在前，可选参数在后

### 3. 输出格式规范
- 默认输出简洁易读
- 提供机器可解析的输出格式
- 错误信息明确且有用
- 支持管道和重定向

### 4. 交互设计规范
- 重要操作需要确认
- 提供清晰的进度反馈
- 错误处理友好
- 支持批量操作

## 标准命令设计

### 基础命令
```bash
# 显示版本信息
dwrg --version
dwrg -V

# 显示帮助信息
dwrg --help
dwrg -h

# 显示详细帮助
dwrg help <command>
dwrg man <command>

# 显示命令用法
dwrg <command> --usage
```

### 账号管理命令
```bash
# 添加账号
dwrg account add --username <用户名> --password <密码> [--server <渠道服>]

# 列出所有账号
dwrg account list [--server <渠道服>] [--format <格式>]

# 切换当前账号
dwrg account switch <账号ID>

# 删除账号
dwrg account remove <账号ID>

# 显示账号状态
dwrg account status <账号ID>

# 账号登录
dwrg account login <账号ID>

# 账号登出
dwrg account logout
```

### 渠道服管理命令
```bash
# 列出所有渠道服
dwrg server list [--format <格式>]

# 显示当前渠道服
dwrg server current

# 检测渠道服状态
dwrg server detect

# 切换渠道服
dwrg server switch <渠道服名称> [--force]

# 显示渠道服信息
dwrg server show <渠道服名称>

# 设置默认渠道服
dwrg server set-default <渠道服名称>
```

### 资源管理命令
```bash
# 检查游戏文件完整性
dwrg resource check [--server <渠道服>]

# 更新游戏资源
dwrg resource update [--server <渠道服>] [--force]

# 清理缓存
dwrg resource clean [--all]

# 显示缓存信息
dwrg resource info [--server <渠道服>]

# 验证游戏文件
dwrg resource verify [--server <渠道服>]
```

### 启动管理命令
```bash
# 启动游戏
dwrg launch [--account <账号ID>] [--server <渠道服>] [--verbose]

# 启动诊断
dwrg diagnose [--output <文件>]

# 显示启动状态
dwrg status

# 停止游戏进程
dwrg stop [--force]
```

### 配置管理命令
```bash
# 显示配置
dwrg config show [--key <键>] [--format <格式>]

# 设置配置值
dwrg config set <键> <值>

# 删除配置项
dwrg config unset <键>

# 重置配置
dwrg config reset [--all]

# 导出配置
dwrg config export [--output <文件>] [--format <格式>]

# 导入配置
dwrg config import [--input <文件>] [--format <格式>]
```

## 输出格式设计

### 1. 默认格式（人类可读）
```bash
$ dwrg server list
官方服    active    1.0.0    CN
B服      active    1.0.0    CN
测试服   inactive  1.0.0    CN
```

### 2. JSON格式（机器可解析）
```bash
$ dwrg server list --format json
{
  "servers": [
    {
      "name": "官方服",
      "status": "active",
      "version": "1.0.0",
      "region": "CN"
    },
    {
      "name": "B服",
      "status": "active", 
      "version": "1.0.0",
      "region": "CN"
    }
  ]
}
```

### 3. 表格格式（清晰易读）
```bash
$ dwrg account list --format table
+----------+-----------+---------+---------------------+
| 账号ID   | 用户名    | 渠道服  | 最后登录时间        |
+----------+-----------+---------+---------------------+
| acc123   | player1   | 官方服  | 2026-09-21 10:30:00 |
| acc456   | player2   | B服     | 2026-09-21 09:15:00 |
+----------+-----------+---------+---------------------+
```

## 交互式设计

### 1. 确认提示
```bash
$ dwrg server switch B服
即将切换到B服，当前游戏进程将被终止。
是否继续？[y/N]: y
```

### 2. 进度反馈
```bash
$ dwrg resource update
正在检查更新... [████████████████] 100%
下载更新包... ████████████ 75%
完成！
```

### 3. 错误处理
```bash
$ dwrg server switch invalid-server
错误：无效的渠道服名称 'invalid-server'
可用渠道服：官方服, B服, 测试服
```

## 高级功能

### 1. 批量操作
```bash
# 批量添加账号
dwrg account add --file accounts.txt

# 批量切换渠道服
dwrg server switch --all official
```

### 2. 条件过滤
```bash
# 只显示活跃的账号
dwrg account list --status active

# 只显示特定版本的渠道服
dwrg server list --version 1.0.0
```

### 3. 管道支持
```bash
# 过滤活跃的渠道服
dwrg server list | grep active

# 统计账号数量
dwrg account list | wc -l
```

## 配置文件支持

### 1. 全局配置
```bash
~/.config/dwrg/config
```

### 2. 项目配置
```bash
./.dwrg/config
```

### 3. 环境变量
```bash
export DWRG_SERVER=official
export DWRG_ACCOUNT=acc123
```

## 实现建议

### 1. 使用Click框架
```python
import click

@click.group()
@click.version_option(version="1.0.0")
@click.option('--verbose', '-v', is_flag=True, help='详细输出')
def cli(verbose):
    """第五人格命令行管理器"""
    pass

@cli.group()
def account():
    """账号管理"""
    pass

@account.command()
@click.option('--username', '-u', required=True, help='用户名')
@click.option('--password', '-p', required=True, help='密码')
@click.option('--server', '-s', help='渠道服')
def add(username, password, server):
    """添加账号"""
    pass
```

### 2. 参数验证
```python
import click

@click.command()
@click.argument('server_name', type=click.Choice(['official', 'bserver', 'test']))
def switch(server_name):
    """切换渠道服"""
    pass
```

### 3. 输出格式化
```python
import json
import tabulate

def format_output(data, format_type='table'):
    if format_type == 'json':
        return json.dumps(data, indent=2, ensure_ascii=False)
    elif format_type == 'table':
        return tabulate.tabulate(data, headers='keys', tablefmt='grid')
    else:
        return str(data)
```

## 与现有工具对比

### 1. 与git命令对比
```bash
# git
git status
git add file.txt
git commit -m "message"

# dwrg
dwrg status
dwrg account add --username user
dwrg server switch official
```

### 2. 与docker命令对比
```bash
# docker
docker ps
docker run image
docker stop container

# dwrg
dwrg server list
dwrg launch
dwrg stop
```

### 3. 与npm命令对比
```bash
# npm
npm install
npm run build
npm test

# dwrg
dwrg resource update
dwrg launch
dwrg diagnose
```

## 最佳实践

### 1. 命令一致性
- 相似操作使用相似的命令结构
- 参数命名保持一致
- 错误信息格式统一

### 2. 用户友好性
- 提供清晰的错误信息
- 支持自动补全
- 提供详细的使用示例

### 3. 可扩展性
- 预留未来扩展空间
- 支持插件系统
- 保持向后兼容性

### 4. 性能考虑
- 快速响应
- 最小化内存使用
- 支持批量操作

## 总结

这个设计严格遵循Linux命令规范，确保：
- 命令名称简洁明了
- 参数设计符合标准
- 输出格式规范统一
- 交互体验友好自然
- 支持高级功能特性

这样的设计让用户能够快速上手，同时保持专业性和可扩展性。