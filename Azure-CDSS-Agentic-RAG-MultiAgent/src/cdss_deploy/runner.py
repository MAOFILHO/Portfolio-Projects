"""Subprocess wrapper for shell scripts with real-time output streaming."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from cdss_deploy.console import console, stream_output


@dataclass
class RunResult:
    returncode: int
    stdout: str
    stderr: str

    @property
    def success(self) -> bool:
        return self.returncode == 0


def run_script(
    script_path: Path,
    args: list[str] | None = None,
    env_overrides: dict[str, str] | None = None,
    cwd: Path | None = None,
    auto_confirm: bool = True,
    timeout: int = 2400,
) -> RunResult:
    if not script_path.exists():
        return RunResult(returncode=1, stdout="", stderr=f"Script not found: {script_path}")

    cmd = ["bash", str(script_path)]
    if args:
        cmd.extend(args)

    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)

    stdin_data = None
    if auto_confirm:
        stdin_data = "yes\nyes\n"

    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE if stdin_data else None,
            cwd=str(cwd) if cwd else None,
            env=env,
            text=True,
            bufsize=1,
        )

        if stdin_data and proc.stdin:
            proc.stdin.write(stdin_data)
            proc.stdin.close()

        if proc.stdout:
            for line in proc.stdout:
                stdout_lines.append(line)
                stream_output(line)

        if proc.stderr:
            stderr_lines = proc.stderr.readlines()

        proc.wait(timeout=timeout)

        return RunResult(
            returncode=proc.returncode,
            stdout="".join(stdout_lines),
            stderr="".join(stderr_lines),
        )

    except subprocess.TimeoutExpired:
        proc.kill()
        return RunResult(returncode=124, stdout="".join(stdout_lines), stderr="Timeout exceeded")
    except Exception as e:
        return RunResult(returncode=1, stdout="".join(stdout_lines), stderr=str(e))


def run_az(
    args: list[str],
    parse_json: bool = True,
    env_overrides: dict[str, str] | None = None,
    timeout: int = 120,
) -> RunResult:
    cmd = ["az"] + args
    if parse_json and "-o" not in args and "--output" not in args:
        cmd.extend(["-o", "json"])

    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
        return RunResult(
            returncode=result.returncode,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
        )
    except subprocess.TimeoutExpired:
        return RunResult(returncode=124, stdout="", stderr="az command timed out")
    except Exception as e:
        return RunResult(returncode=1, stdout="", stderr=str(e))


def run_cmd(
    cmd: list[str],
    cwd: Path | None = None,
    env_overrides: dict[str, str] | None = None,
    stream: bool = False,
    timeout: int = 600,
) -> RunResult:
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)

    if stream:
        stdout_lines: list[str] = []
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(cwd) if cwd else None,
                env=env,
                text=True,
                bufsize=1,
            )
            if proc.stdout:
                for line in proc.stdout:
                    stdout_lines.append(line)
                    stream_output(line)
            stderr_data = proc.stderr.read() if proc.stderr else ""
            proc.wait(timeout=timeout)
            return RunResult(proc.returncode, "".join(stdout_lines), stderr_data)
        except subprocess.TimeoutExpired:
            proc.kill()
            return RunResult(124, "".join(stdout_lines), "Timeout exceeded")
    else:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=str(cwd) if cwd else None,
                env=env,
                timeout=timeout,
            )
            return RunResult(result.returncode, result.stdout.strip(), result.stderr.strip())
        except subprocess.TimeoutExpired:
            return RunResult(124, "", "Command timed out")
        except Exception as e:
            return RunResult(1, "", str(e))
