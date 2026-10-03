"""
CLI命令定义
"""


import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .accounts.manager import AccountManager
from .config.manager import ConfigManager
from .launcher.manager import LauncherManager
from .resources.manager import ResourceManager
from .servers.manager import ServerManager
from .utils.logger import get_logger

# 创建日志器
logger = get_logger(__name__)
console = Console()

# 创建控制台
console = Console()

# 设置日志
setup_logging()

# 创建主应用
app = typer.Typer(
    name="dwrg",
    help="第五人格游戏多渠道服和多账号管理工具",
    add_completion=False,
)

# 创建子命令组
account_app = typer.Typer(help="账号管理")
server_app = typer.Typer(help="渠道服管理")
resource_app = typer.Typer(help="资源管理")
launch_app = typer.Typer(help="启动管理")
config_app = typer.Typer(help="配置管理")
plugin_app = typer.Typer(help="插件管理")

# 添加子命令
app.add_typer(account_app, name="account")
app.add_typer(server_app, name="server")
app.add_typer(resource_app, name="resource")
app.add_typer(launch_app, name="launch")
app.add_typer(config_app, name="config")
app.add_typer(plugin_app, name="plugin")

# ==================== 账号管理 ====================

@account_app.command("add")
def add_account(
    username: str = typer.Option(..., "--username", "-u", help="用户名"),
    password: str = typer.Option(..., "--password", "-p", help="密码"),
    server: str = typer.Option("official", "--server", "-s", help="渠道服"),
):
    """添加账号"""
    try:
        account_manager = AccountManager()
        account = account_manager.create_account(username, server, password)
        rprint(f"[green]✓[/green] 账号添加成功: {account.username}")
    except Exception as e:
        rprint(f"[red]✗[/red] 账号添加失败: {e}")
        raise typer.Exit(1)

@account_app.command("list")
def list_accounts(
    server: str | None = typer.Option(None, "--server", "-s", help="渠道服"),
    format: str = typer.Option("table", "--format", "-f", help="输出格式"),
):
    """列出账号"""
    try:
        account_manager = AccountManager()
        accounts = account_manager.list_accounts(server)

        if format == "json":
            import json
            rprint(json.dumps([acc.dict() for acc in accounts], indent=2, ensure_ascii=False))
        elif format == "table":
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("账号ID", style="cyan")
            table.add_column("用户名", style="green")
            table.add_column("渠道服", style="yellow")
            table.add_column("最后登录", style="white")

            for acc in accounts:
                table.add_row(
                    acc.id[:8] + "..." if len(acc.id) > 8 else acc.id,
                    acc.username,
                    acc.server,
                    acc.last_login.strftime("%Y-%m-%d %H:%M") if acc.last_login else "从未登录"
                )

            console.print(table)
        else:
            for acc in accounts:
                rprint(f"[cyan]{acc.id[:8]}...[/cyan] {acc.username} - {acc.server}")
    except Exception as e:
        rprint(f"[red]✗[/red] 列出账号失败: {e}")
        raise typer.Exit(1)

@account_app.command("switch")
def switch_account(account_id: str):
    """切换账号"""
    try:
        account_manager = AccountManager()
        success = account_manager.switch_account(account_id)
        if success:
            rprint("[green]✓[/green] 账号切换成功")
        else:
            rprint("[red]✗[/red] 账号切换失败")
            raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]✗[/red] 账号切换失败: {e}")
        raise typer.Exit(1)

@account_app.command("remove")
def remove_account(
    account_id: str,
    force: bool = typer.Option(False, "--force", "-f", help="强制删除"),
):
    """删除账号"""
    if not force:
        confirm = typer.confirm(f"确定要删除账号 {account_id} 吗？")
        if not confirm:
            rprint("[yellow]取消删除[/yellow]")
            raise typer.Exit(0)

    try:
        account_manager = AccountManager()
        success = account_manager.remove_account(account_id)
        if success:
            rprint("[green]✓[/green] 账号删除成功")
        else:
            rprint("[red]✗[/red] 账号删除失败")
            raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]✗[/red] 账号删除失败: {e}")
        raise typer.Exit(1)

# ==================== 渠道服管理 ====================

@server_app.command("list")
def list_servers(
    format: str = typer.Option("table", "--format", "-f", help="输出格式"),
):
    """列出渠道服"""
    try:
        server_manager = ServerManager()
        servers = server_manager.list_servers()

        if format == "json":
            import json
            rprint(json.dumps([srv.dict() for srv in servers], indent=2, ensure_ascii=False))
        elif format == "table":
            table = Table(show_header=True, header_style="bold magenta")
            table.add_column("名称", style="cyan")
            table.add_column("状态", style="green")
            table.add_column("版本", style="yellow")
            table.add_column("地区", style="white")

            for srv in servers:
                status_color = "green" if srv.status == "active" else "red"
                table.add_row(
                    srv.name,
                    f"[{status_color}]{srv.status}[/{status_color}]",
                    srv.version,
                    srv.region
                )

            console.print(table)
        else:
            for srv in servers:
                rprint(f"[cyan]{srv.name}[/cyan] - {srv.status} ({srv.version})")
    except Exception as e:
        rprint(f"[red]✗[/red] 列出渠道服失败: {e}")
        raise typer.Exit(1)

@server_app.command("current")
def current_server():
    """显示当前渠道服"""
    try:
        server_manager = ServerManager()
        current = server_manager.get_current_server()
        if current:
            rprint(f"[cyan]当前渠道服:[/cyan] {current.name} ({current.version})")
        else:
            rprint("[yellow]未设置当前渠道服[/yellow]")
    except Exception as e:
        rprint(f"[red]✗[/red] 获取当前渠道服失败: {e}")
        raise typer.Exit(1)

@server_app.command("switch")
def switch_server(
    server_name: str,
    force: bool = typer.Option(False, "--force", "-f", help="强制切换"),
):
    """切换渠道服"""
    if not force:
        confirm = typer.confirm(f"确定要切换到 {server_name} 吗？")
        if not confirm:
            rprint("[yellow]取消切换[/yellow]")
            raise typer.Exit(0)

    try:
        server_manager = ServerManager()
        success = server_manager.switch_server(server_name)
        if success:
            rprint("[green]✓[/green] 渠道服切换成功")
        else:
            rprint("[red]✗[/red] 渠道服切换失败")
            raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]✗[/red] 渠道服切换失败: {e}")
        raise typer.Exit(1)

@server_app.command("show")
def show_server(server_name: str):
    """显示渠道服信息"""
    try:
        server_manager = ServerManager()
        server = server_manager.get_server(server_name)
        if server:
            panel = Panel(
                f"[cyan]名称:[/cyan] {server.name}\n"
                f"[green]状态:[/green] {server.status}\n"
                f"[yellow]版本:[/yellow] {server.version}\n"
                f"[white]地区:[/white] {server.region}\n"
                f"[blue]地址:[/blue] {server.endpoint}",
                title=f"渠道服信息 - {server.name}",
                border_style="blue"
            )
            console.print(panel)
        else:
            rprint(f"[red]✗[/red] 未找到渠道服: {server_name}")
            raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]✗[/red] 显示渠道服信息失败: {e}")
        raise typer.Exit(1)

# ==================== 资源管理 ====================

@resource_app.command("check")
def check_resources(
    server: str | None = typer.Option(None, "--server", "-s", help="渠道服"),
):
    """检查游戏资源"""
    try:
        resource_manager = ResourceManager()
        result = resource_manager.check_resources(server)

        panel = Panel(
            f"[green]检查结果:[/green]\n"
            f"文件总数: {result.total_files}\n"
            f"正常文件: {result.healthy_files}\n"
            f"损坏文件: {result.corrupted_files}\n"
            f"缺失文件: {result.missing_files}",
            title="资源检查结果",
            border_style="blue"
        )
        console.print(panel)
    except Exception as e:
        rprint(f"[red]✗[/red] 检查资源失败: {e}")
        raise typer.Exit(1)

@resource_app.command("update")
def update_resources(
    server: str | None = typer.Option(None, "--server", "-s", help="渠道服"),
    force: bool = typer.Option(False, "--force", "-f", help="强制更新"),
):
    """更新游戏资源"""
    try:
        resource_manager = ResourceManager()
        result = resource_manager.update_resources(server, force)

        if result.success:
            rprint("[green]✓[/green] 资源更新成功")
        else:
            rprint(f"[red]✗[/red] 资源更新失败: {result.error}")
            raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]✗[/red] 更新资源失败: {e}")
        raise typer.Exit(1)

@resource_app.command("clean")
def clean_resources(
    all: bool = typer.Option(False, "--all", "-a", help="清理所有缓存"),
):
    """清理缓存"""
    try:
        resource_manager = ResourceManager()
        success = resource_manager.clean_cache(all)
        if success:
            rprint("[green]✓[/green] 缓存清理成功")
        else:
            rprint("[red]✗[/red] 缓存清理失败")
            raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]✗[/red] 清理缓存失败: {e}")
        raise typer.Exit(1)

# ==================== 启动管理 ====================

@launch_app.command()
def launch_game(
    account: str | None = typer.Option(None, "--account", "-a", help="账号ID"),
    server: str | None = typer.Option(None, "--server", "-s", help="渠道服"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="详细输出"),
):
    """启动游戏"""
    try:
        launcher = LauncherManager()
        success = launcher.launch_game(account, server, verbose)
        if success:
            rprint("[green]✓[/green] 游戏启动成功")
        else:
            rprint("[red]✗[/red] 游戏启动失败")
            raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]✗[/red] 启动游戏失败: {e}")
        raise typer.Exit(1)

@launch_app.command("stop")
def stop_game(
    force: bool = typer.Option(False, "--force", "-f", help="强制停止"),
):
    """停止游戏"""
    try:
        launcher = LauncherManager()
        success = launcher.stop_game(force)
        if success:
            rprint("[green]✓[/green] 游戏停止成功")
        else:
            rprint("[red]✗[/red] 游戏停止失败")
            raise typer.Exit(1)
    except Exception as e:
        rprint(f"[red]✗[/red] 停止游戏失败: {e}")
        raise typer.Exit(1)

# ==================== 配置管理 ====================

@config_app.command("show")
def show_config(
    key: str | None = typer.Option(None, "--key", "-k", help="配置键"),
    format: str = typer.Option("table", "--format", "-f", help="输出格式"),
):
    """显示配置"""
    try:
        config_manager = ConfigManager()
        config = config_manager.get_config()

        if key:
            value = config.get(key)
            if value is not None:
                rprint(f"[cyan]{key}:[/cyan] {value}")
            else:
                rprint(f"[yellow]配置项 {key} 不存在[/yellow]")
        else:
            if format == "json":
                import json
                rprint(json.dumps(config, indent=2, ensure_ascii=False))
            elif format == "table":
                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("键", style="cyan")
                table.add_column("值", style="white")

                for k, v in config.items():
                    table.add_row(k, str(v))

                console.print(table)
            else:
                for k, v in config.items():
                    rprint(f"[cyan]{k}:[/cyan] {v}")
    except Exception as e:
        rprint(f"[red]✗[/red] 显示配置失败: {e}")
        raise typer.Exit(1)

@config_app.command("set")
def set_config(key: str, value: str):
    """设置配置"""
    try:
        config_manager = ConfigManager()
        config_manager.set_config(key, value)
        rprint(f"[green]✓[/green] 配置设置成功: {key} = {value}")
    except Exception as e:
        rprint(f"[red]✗[/red] 设置配置失败: {e}")
        raise typer.Exit(1)

@config_app.command("unset")
def unset_config(key: str):
    """删除配置项"""
    try:
        config_manager = ConfigManager()
        config_manager.unset_config(key)
        rprint(f"[green]✓[/green] 配置删除成功: {key}")
    except Exception as e:
        rprint(f"[red]✗[/red] 删除配置失败: {e}")
        raise typer.Exit(1)

# ==================== 插件管理 ====================

@plugin_app.command("list")
def list_plugins(
    format: str = typer.Option("table", "--format", "-f", help="输出格式"),
):
    """列出插件"""
    try:
        # 这里需要实现插件管理器
        rprint("[yellow]插件管理功能开发中...[/yellow]")
    except Exception as e:
        rprint(f"[red]✗[/red] 列出插件失败: {e}")
        raise typer.Exit(1)

# ==================== 系统命令 ====================

@app.command("diagnose")
def diagnose_system(
    output: str | None = typer.Option(None, "--output", "-o", help="输出文件"),
):
    """系统诊断"""
    try:
        # 这里需要实现系统诊断功能
        rprint("[yellow]系统诊断功能开发中...[/yellow]")
    except Exception as e:
        rprint(f"[red]✗[/red] 系统诊断失败: {e}")
        raise typer.Exit(1)

@app.command("status")
def show_status():
    """显示状态"""
    try:
        # 这里需要实现状态显示功能
        rprint("[yellow]状态显示功能开发中...[/yellow]")
    except Exception as e:
        rprint(f"[red]✗[/red] 显示状态失败: {e}")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()
