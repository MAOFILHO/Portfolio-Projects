"""Streaming subprocess wrapper for az / func / npm / bicep invocations.

Streams stdout/stderr live (so the user sees exactly which long-running az
command is executing) while also capturing the full output for callers that
need to parse JSON results (e.g. `az deployment sub create ... -o json`).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from surveil_deploy.console import console


class CommandError(RuntimeError):
    def __init__(self, command: list[str], returncode: int, output: str) -> None:
        self.command = command
        self.returncode = returncode
        self.output = output
        super().__init__(f"Command failed ({returncode}): {' '.join(command)}")


@dataclass
class CommandResult:
    returncode: int
    stdout: str


def run(
    command: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    stream: bool = True,
    check: bool = True,
    timeout: int | None = None,
) -> CommandResult:
    """Run a command, optionally streaming its output live to the console.

    Always returns full captured stdout (for JSON parsing) regardless of
    whether streaming is enabled.
    """
    import os

    full_env = {**os.environ, **(env or {})}

    if stream:
        console.print(f"    [dim]$ {' '.join(command)}[/dim]")
        process = subprocess.Popen(
            command,
            cwd=str(cwd) if cwd else None,
            env=full_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        lines: list[str] = []
        assert process.stdout is not None
        for line in process.stdout:
            lines.append(line)
            console.print(f"    [dim]{line.rstrip()}[/dim]")
        process.wait(timeout=timeout)
        output = "".join(lines)
        result = CommandResult(returncode=process.returncode, stdout=output)
    else:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            env=full_env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        result = CommandResult(returncode=completed.returncode, stdout=completed.stdout + completed.stderr)

    if check and result.returncode != 0:
        raise CommandError(command, result.returncode, result.stdout)

    return result


def run_json(
    command: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int | None = None,
) -> dict:
    """Run a command whose stdout is pure JSON (e.g. `az ... -o json`).

    stderr is streamed live to the console (Azure CLI writes progress/warning
    text there) while stdout is captured separately and parsed as JSON —
    avoids the fragility of trying to locate a JSON object inside merged
    stdout+stderr text.
    """
    import json
    import os
    import threading

    full_env = {**os.environ, **(env or {})}
    console.print(f"    [dim]$ {' '.join(command)}[/dim]")

    process = subprocess.Popen(
        command,
        cwd=str(cwd) if cwd else None,
        env=full_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    def _stream_stderr() -> None:
        assert process.stderr is not None
        for line in process.stderr:
            if line.strip():
                console.print(f"    [dim]{line.rstrip()}[/dim]")

    stderr_thread = threading.Thread(target=_stream_stderr, daemon=True)
    stderr_thread.start()

    assert process.stdout is not None
    stdout = process.stdout.read()
    process.wait(timeout=timeout)
    stderr_thread.join(timeout=5)

    if process.returncode != 0:
        raise CommandError(command, process.returncode, stdout)

    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise CommandError(command, 0, f"Failed to parse JSON output: {exc}\nRaw stdout: {stdout[:2000]}") from exc


def tool_version(command: list[str]) -> str | None:
    try:
        result = run(command, stream=False, check=False, timeout=15)
        if result.returncode != 0:
            return None
        return result.stdout.strip().splitlines()[0] if result.stdout.strip() else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
