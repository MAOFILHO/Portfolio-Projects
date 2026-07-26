"""Descriptive terminal output for the deployment pipeline.

Ports the visual vocabulary of Video-Agents-Foundry-Solution/hooks/ui.sh
(log_step / write_health_row / write_summary_block) from bash to Rich, so
every stage of `surveil-deploy` prints a clearly numbered, colored step
header and every smoke/health check renders as an aligned status row —
matching the "descriptive terminal output" requirement.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

SYM_SUCCESS = "✔"  # ✔
SYM_ERROR = "✘"  # ✘
SYM_WARNING = "⚠"  # ⚠
SYM_INFO = "•"  # •
SYM_STEP = "▶"  # ▶


class HealthStatus(str, Enum):
    PASS = "Pass"
    FAIL = "Fail"
    WARN = "Warn"
    PENDING = "Pending"
    SKIP = "Skip"


_STATUS_STYLE = {
    HealthStatus.PASS: ("green", SYM_SUCCESS),
    HealthStatus.FAIL: ("red", SYM_ERROR),
    HealthStatus.WARN: ("yellow", SYM_WARNING),
    HealthStatus.PENDING: ("dim", "○"),
    HealthStatus.SKIP: ("dim", "─"),
}


def write_banner(title: str, subtitle: str = "") -> None:
    body = f"[bold white]{title}[/bold white]"
    if subtitle:
        body += f"\n[dim]{subtitle}[/dim]"
    console.print(Panel(body, border_style="cyan", expand=False))


def write_title(text: str) -> None:
    console.print(f"\n[bold cyan]{text}[/bold cyan]")


def write_section(text: str) -> None:
    console.print(f"\n[bold]❯ {text}[/bold]")


def log_step(number: int, total: int, title: str) -> None:
    rule = "─" * max(len(title) + 10, 20)
    console.print(f"\n  [bold cyan]{SYM_STEP}[/bold cyan]  [dim][{number}/{total}][/dim]  [bold white]{title}[/bold white]")
    console.print(f"  [dim]{rule}[/dim]")


def log_info(message: str) -> None:
    console.print(f"  [cyan]{SYM_INFO}[/cyan] {message}")


def log_success(message: str) -> None:
    console.print(f"  [green]{SYM_SUCCESS}[/green] {message}")


def log_warning(message: str) -> None:
    console.print(f"  [yellow]{SYM_WARNING}[/yellow] {message}")


def log_error(message: str) -> None:
    console.print(f"  [red]{SYM_ERROR}[/red] {message}")


def write_key_value(key: str, value: str) -> None:
    console.print(f"    [dim]{key}:[/dim] [white]{value}[/white]")


@dataclass
class HealthRow:
    name: str
    status: HealthStatus
    detail: str = ""


def write_health_row(row: HealthRow) -> None:
    style, symbol = _STATUS_STYLE[row.status]
    console.print(f"    [{style}]{symbol}[/{style}]  {row.name:<32} [dim]{row.detail}[/dim]")


def write_summary_block(rows: list[HealthRow], title: str = "Summary") -> bool:
    passed = sum(1 for r in rows if r.status == HealthStatus.PASS)
    failed = sum(1 for r in rows if r.status == HealthStatus.FAIL)
    warnings = sum(1 for r in rows if r.status == HealthStatus.WARN)
    total = len(rows)

    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_row("[green]Passed[/green]", str(passed))
    table.add_row("[red]Failed[/red]", str(failed))
    table.add_row("[yellow]Warnings[/yellow]", str(warnings))
    table.add_row("[bold]Total[/bold]", str(total))

    all_ok = failed == 0
    border_style = "green" if all_ok else "red"
    heading = f"[bold green]{title}: All Checks Passed[/bold green]" if all_ok else f"[bold red]{title}: Issues Detected[/bold red]"
    console.print(Panel(table, title=heading, border_style=border_style, expand=False))
    return all_ok
