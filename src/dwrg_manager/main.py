"""
主入口文件
"""

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .utils.logger import setup_logging
from .utils.version import get_version

# 创建控制台
console = Console()

# 设置日志
setup_logging()

# 创建应用
cli_app = typer.Typer(
    name="dwrg",
    help="第五人格游戏多渠道服和多账号管理工具",
    add_completion=False,
)

@cli_app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="显示版本信息",
        is_eager=True,
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="详细输出",
    ),
):
    """第五人格命令行管理器"""
    if version:
        rprint(f"[bold green]DWRG CLI Manager[/bold green] 版本: {get_version()}")
        raise typer.Exit()

    if verbose:
        console.print("[yellow]详细输出模式已启用[/yellow]")

@cli_app.command()
def help_command():
    """显示详细帮助信息"""
    table = Table(show_header=False, box=None)
    table.add_column("命令", style="cyan")
    table.add_column("描述", style="white")

    commands = [
        ("account", "账号管理"),
        ("server", "渠道服管理"),
        ("resource", "资源管理"),
        ("launch", "启动管理"),
        ("config", "配置管理"),
        ("plugin", "插件管理"),
        ("diagnose", "系统诊断"),
        ("status", "状态检查"),
    ]

    for cmd, desc in commands:
        table.add_row(f"[bold]{cmd}[/bold]", desc)

    console.print(Panel(table, title="可用命令", border_style="blue"))

if __name__ == "__main__":
    cli_app()
