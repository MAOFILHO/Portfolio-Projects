"""Rich console helpers for step-by-step terminal output."""

from __future__ import annotations

import time

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

STEP_ICONS = {
    "pending": "[dim]○[/dim]",
    "in_progress": "[yellow]◉[/yellow]",
    "completed": "[green]✓[/green]",
    "failed": "[red]✗[/red]",
    "skipped": "[dim]⊘[/dim]",
}


def print_banner() -> None:
    banner = Text.from_markup(
        "[bold cyan]Azure CDSS Pipeline[/bold cyan]\n"
        "[dim]Automated Clinical Decision Support System Deployment[/dim]\n"
        "[dim]Zero Azure Portal Clicks[/dim]"
    )
    console.print(Panel(banner, border_style="cyan", padding=(1, 2)))


def print_step_start(step_num: int, total: int, description: str) -> None:
    console.print()
    console.rule(f"[bold]Step {step_num}/{total}: {description}[/bold]", style="cyan")


def print_step_done(step_num: int, description: str, elapsed: float) -> None:
    console.print(
        f"  [green]✓[/green] {description} [dim]({elapsed:.1f}s)[/dim]"
    )


def print_step_skip(step_num: int, description: str) -> None:
    console.print(f"  [dim]⊘ {description} (already completed, skipping)[/dim]")


def print_step_fail(step_num: int, description: str, error: str) -> None:
    console.print(f"  [red]✗ {description}[/red]")
    console.print(f"    [red]Error: {error}[/red]")


def print_substep(message: str, status: str = "info") -> None:
    icon = {"info": "[blue]→[/blue]", "ok": "[green]✓[/green]", "warn": "[yellow]![/yellow]", "error": "[red]✗[/red]"}.get(status, "→")
    console.print(f"    {icon} {message}")


def print_deployment_summary(resources: dict) -> None:
    table = Table(title="Deployment Summary", border_style="cyan")
    table.add_column("Resource", style="bold")
    table.add_column("Value", style="dim")
    for key, value in resources.items():
        table.add_row(key, str(value))
    console.print()
    console.print(table)


def print_status_table(steps: dict) -> None:
    table = Table(title="Deployment Status", border_style="cyan")
    table.add_column("#", width=3)
    table.add_column("Step", min_width=30)
    table.add_column("Status", width=12)
    table.add_column("Duration", width=10)

    for i, (name, rec) in enumerate(steps.items()):
        icon = STEP_ICONS.get(rec.status, "?")
        duration = ""
        if rec.started_at and rec.completed_at:
            from datetime import datetime, timezone

            start = datetime.fromisoformat(rec.started_at)
            end = datetime.fromisoformat(rec.completed_at)
            duration = f"{(end - start).total_seconds():.1f}s"
        table.add_row(str(i), name, f"{icon} {rec.status}", duration)

    console.print()
    console.print(table)


def stream_output(line: str) -> None:
    console.print(f"    [dim]│[/dim] {line.rstrip()}")


class StepTimer:
    def __init__(self) -> None:
        self._start: float = 0

    def __enter__(self) -> StepTimer:
        self._start = time.monotonic()
        return self

    def __exit__(self, *_: object) -> None:
        pass

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._start
