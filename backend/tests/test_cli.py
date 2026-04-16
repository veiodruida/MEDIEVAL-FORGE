"""Tests for medieval_forge.cli."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from medieval_forge.cli import PID_FILE, cli


def test_help_lists_start_and_stop():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "start" in result.output
    assert "stop" in result.output


def test_start_no_browser(tmp_path, monkeypatch):
    """`start --no-browser --port N`: webbrowser.open MUST NOT be called; uvicorn.run MUST be called."""
    # Redirect PID_FILE to tmp_path so the test doesn't pollute ~/.medieval-forge
    fake_pid = tmp_path / "medieval_forge.pid"
    monkeypatch.setattr("medieval_forge.cli.PID_FILE", fake_pid)
    with patch("medieval_forge.cli.uvicorn.run") as mock_run, patch(
        "medieval_forge.cli.webbrowser.open"
    ) as mock_browser:
        runner = CliRunner()
        result = runner.invoke(cli, ["start", "--no-browser", "--port", "9999"])
        assert result.exit_code == 0, result.output
        mock_run.assert_called_once()
        kwargs = mock_run.call_args.kwargs
        assert kwargs["host"] == "127.0.0.1"
        assert kwargs["port"] == 9999
        mock_browser.assert_not_called()


def test_pid_file(tmp_path, monkeypatch):
    """`start` writes the current PID to PID_FILE before invoking uvicorn."""
    fake_pid = tmp_path / "medieval_forge.pid"
    monkeypatch.setattr("medieval_forge.cli.PID_FILE", fake_pid)
    with patch("medieval_forge.cli.uvicorn.run"):
        runner = CliRunner()
        result = runner.invoke(cli, ["start", "--no-browser"])
        assert result.exit_code == 0, result.output
    # After uvicorn.run is mocked (returns immediately), the finally clause
    # unlinks the PID file. To assert the write happened, capture it from
    # the mock context. Simpler: re-invoke with a capturing patch.
    captured = {}

    def fake_run(*args, **kwargs):
        captured["pid"] = fake_pid.read_text().strip()

    with patch("medieval_forge.cli.uvicorn.run", side_effect=fake_run):
        runner = CliRunner()
        result = runner.invoke(cli, ["start", "--no-browser"])
        assert result.exit_code == 0
    assert captured["pid"] == str(os.getpid())


def test_stop_command_no_pid_file(tmp_path, monkeypatch):
    """`stop` with no PID file prints helpful message and exits 0."""
    fake_pid = tmp_path / "medieval_forge.pid"
    monkeypatch.setattr("medieval_forge.cli.PID_FILE", fake_pid)
    runner = CliRunner()
    result = runner.invoke(cli, ["stop"])
    assert result.exit_code == 0
    assert "No running server found" in result.output


def test_stop_command_terminates_process(tmp_path, monkeypatch):
    """`stop` calls psutil.Process(pid).terminate() and unlinks PID file."""
    fake_pid = tmp_path / "medieval_forge.pid"
    fake_pid.write_text("12345")
    monkeypatch.setattr("medieval_forge.cli.PID_FILE", fake_pid)

    with patch("medieval_forge.cli.psutil.Process") as mock_proc_cls:
        mock_proc = mock_proc_cls.return_value
        runner = CliRunner()
        result = runner.invoke(cli, ["stop"])
        assert result.exit_code == 0
        mock_proc_cls.assert_called_once_with(12345)
        mock_proc.terminate.assert_called_once()
    assert not fake_pid.exists()
