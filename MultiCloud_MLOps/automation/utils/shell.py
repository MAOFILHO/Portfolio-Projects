"""
MultiCloud MLOps - Shared Utilities
CLI runner, logging, and validation helpers used by every automation module.
"""
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional


# ─── Logging ──────────────────────────────────────────────────────────────────

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S"
            )
        )
        logger.addHandler(h)
    logger.setLevel(logging.INFO)
    return logger


log = get_logger("utils")


# ─── Shell runner ─────────────────────────────────────────────────────────────

def run(
    cmd,
    *,
    capture: bool = False,
    check: bool = True,
    env: Optional[dict] = None,
    cwd: Optional[Path] = None,
    description: str = "",
) -> subprocess.CompletedProcess:
    """
    Run a shell command with consistent logging and error handling.

    cmd         : str (shell=True) or list[str] (shell=False)
    capture     : capture stdout/stderr in result
    check       : raise CalledProcessError on non-zero exit
    env         : extra env vars merged with current environment
    cwd         : working directory
    description : human-readable label for log output
    """
    import os

    label = description or (cmd if isinstance(cmd, str) else " ".join(str(a) for a in cmd))
    log.info("▶ %s", label)

    merged_env = None
    if env:
        merged_env = {**os.environ, **env}

    result = subprocess.run(
        cmd,
        shell=isinstance(cmd, str),
        capture_output=capture,
        text=True,
        check=False,
        env=merged_env,
        cwd=str(cwd) if cwd else None,
    )

    if capture and result.stdout:
        log.debug("stdout: %s", result.stdout.strip()[:500])
    if result.returncode != 0 and result.stderr:
        log.warning("stderr: %s", result.stderr.strip()[:500])

    if check and result.returncode != 0:
        log.error("Command failed (exit %d): %s", result.returncode, label)
        if result.stderr:
            log.error("stderr: %s", result.stderr.strip())
        raise subprocess.CalledProcessError(
            result.returncode, cmd, result.stdout, result.stderr
        )
    return result


def run_json(cmd, **kwargs) -> Any:
    """Run command and parse stdout as JSON."""
    kwargs["capture"] = True
    result = run(cmd, **kwargs)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        log.error("JSON parse error from: %s\n%s", cmd, result.stdout[:200])
        raise RuntimeError(f"JSON parse error: {exc}") from exc


def run_or_skip(cmd, *, description: str = "", **kwargs) -> Optional[subprocess.CompletedProcess]:
    """Run command; log warning and return None on failure (non-fatal)."""
    try:
        return run(cmd, description=description, **kwargs)
    except subprocess.CalledProcessError as exc:
        log.warning("Non-fatal failure skipped: %s — exit %d", description or cmd, exc.returncode)
        return None


# ─── Azure/AWS convenience wrappers ──────────────────────────────────────────

def az(*args: str, capture: bool = True, check: bool = True) -> str:
    cmd = ["az"] + list(args)
    result = run(cmd, capture=capture, check=check, description=" ".join(cmd))
    return result.stdout.strip() if capture else ""


def az_json(*args: str) -> Any:
    cmd = ["az"] + list(args) + ["--output", "json"]
    return run_json(cmd)


def az_exists(check_cmd: list) -> bool:
    return run(check_cmd, capture=True, check=False).returncode == 0


def aws(*args: str, capture: bool = True, check: bool = True) -> str:
    cmd = ["aws"] + list(args)
    result = run(cmd, capture=capture, check=check, description=" ".join(cmd))
    return result.stdout.strip() if capture else ""


def aws_json(*args: str) -> Any:
    cmd = ["aws"] + list(args) + ["--output", "json"]
    return run_json(cmd)


# ─── Tool checks ──────────────────────────────────────────────────────────────

REQUIRED_TOOLS: dict[str, str] = {
    "aws":     "AWS CLI 2.13+   → https://aws.amazon.com/cli",
    "az":      "Azure CLI 2.50+ → https://learn.microsoft.com/cli/azure",
    "kubectl": "kubectl 1.28+   → https://kubernetes.io/docs/tasks/tools",
    "helm":    "Helm 3.12+      → https://helm.sh/docs/intro/install",
    "docker":  "Docker 24+      → https://www.docker.com/products/docker-desktop",
    "node":    "Node.js 20+     → https://nodejs.org",
}


def check_tools(tools: Optional[list[str]] = None) -> bool:
    """Verify required CLI tools are on PATH. Returns True if all present."""
    to_check = tools or list(REQUIRED_TOOLS.keys())
    missing = [t for t in to_check if shutil.which(t) is None]
    if missing:
        log.error("Missing required tools:")
        for t in missing:
            log.error("  ✗ %-10s %s", t, REQUIRED_TOOLS.get(t, ""))
        return False
    log.info("✅ Tools OK: %s", ", ".join(to_check))
    return True


# ─── Misc ─────────────────────────────────────────────────────────────────────

def step(title: str) -> None:
    """Print a visible section header."""
    bar = "─" * 62
    log.info("\n%s\n  %s\n%s", bar, title, bar)


def write_env_file(path: Path, values: dict[str, str], mode: str = "w") -> None:
    with open(path, mode) as f:
        for k, v in values.items():
            if k.startswith("#"):
                f.write(f"\n{k}\n")
            else:
                f.write(f"{k}={v}\n")
    log.info("Written: %s", path)
