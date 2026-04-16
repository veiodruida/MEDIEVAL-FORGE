"""Medieval Forge command-line interface.

Per PKG-02..04: start/stop the FastAPI server with optional browser open.
Uses psutil for cross-platform process termination (RESEARCH.md Assumption A5).
"""
from __future__ import annotations

import os
import threading
import webbrowser
from pathlib import Path

import click
import psutil
import uvicorn

from .database import DATA_DIR

PID_FILE: Path = DATA_DIR / "medieval_forge.pid"


@click.group()
def cli() -> None:
    """Medieval Forge — local map authoring tool."""


@cli.command()
@click.option("--port", default=8765, show_default=True, help="Port to listen on.")
@click.option("--no-browser", is_flag=True, help="Skip opening browser tab.")
def start(port: int, no_browser: bool) -> None:
    """Start the Medieval Forge FastAPI server."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(os.getpid()))

    if not no_browser:
        threading.Timer(
            1.5, lambda: webbrowser.open(f"http://localhost:{port}")
        ).start()

    try:
        uvicorn.run(
            "medieval_forge.main:app",
            host="127.0.0.1",
            port=port,
            log_level="info",
        )
    finally:
        if PID_FILE.exists():
            PID_FILE.unlink(missing_ok=True)


@cli.command()
def stop() -> None:
    """Stop the running Medieval Forge server (reads PID file)."""
    if not PID_FILE.exists():
        click.echo("No running server found.")
        return
    try:
        pid = int(PID_FILE.read_text().strip())
    except ValueError:
        click.echo("PID file corrupt; removing.")
        PID_FILE.unlink(missing_ok=True)
        return

    try:
        proc = psutil.Process(pid)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except psutil.TimeoutExpired:
            proc.kill()
        click.echo(f"Stopped process {pid}")
    except psutil.NoSuchProcess:
        click.echo(f"Process {pid} not running; cleaning PID file.")
    finally:
        PID_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    cli()
