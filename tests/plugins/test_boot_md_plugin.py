"""Tests for the boot_md plugin."""

import importlib
import threading
from pathlib import Path
from unittest import mock

import pytest

import plugins.boot_md as boot_md_mod


@pytest.fixture
def hermes_home(tmp_path):
    """Provide a temporary HERMES_HOME directory."""
    return tmp_path


@pytest.fixture
def boot_file(hermes_home):
    """Return the path where BOOT.md would live."""
    return hermes_home / "BOOT.md"


@pytest.fixture(autouse=True)
def _reset_boot_executed():
    """Reset the _boot_executed flag before each test."""
    boot_md_mod._boot_executed = False
    yield
    boot_md_mod._boot_executed = False


def test_session_start_runs_boot_md(hermes_home, boot_file):
    """BOOT.md exists with content -> thread is started."""
    boot_file.write_text("# Startup\n1. Check logs\n")

    with mock.patch.object(boot_md_mod, "_get_boot_file", return_value=boot_file), \
         mock.patch.object(boot_md_mod, "threading") as mock_threading:
        mock_thread = mock.MagicMock()
        mock_threading.Thread.return_value = mock_thread

        boot_md_mod._on_session_start(session_id="test-session")

        mock_threading.Thread.assert_called_once()
        call_kwargs = mock_threading.Thread.call_args
        assert call_kwargs.kwargs["daemon"] is True
        assert call_kwargs.kwargs["name"] == "boot-md"
        mock_thread.start.assert_called_once()


def test_session_start_skips_if_no_file(hermes_home):
    """No BOOT.md -> thread is never created."""
    missing = hermes_home / "BOOT.md"

    with mock.patch.object(boot_md_mod, "_get_boot_file", return_value=missing), \
         mock.patch.object(boot_md_mod, "threading") as mock_threading:
        boot_md_mod._on_session_start(session_id="test-session")
        mock_threading.Thread.assert_not_called()


def test_session_start_skips_if_empty(hermes_home, boot_file):
    """BOOT.md exists but is empty -> thread is never created."""
    boot_file.write_text("   \n  \n")

    with mock.patch.object(boot_md_mod, "_get_boot_file", return_value=boot_file), \
         mock.patch.object(boot_md_mod, "threading") as mock_threading:
        boot_md_mod._on_session_start(session_id="test-session")
        mock_threading.Thread.assert_not_called()


def test_session_start_runs_in_background_thread(hermes_home, boot_file):
    """Verify threading.Thread is used with daemon=True and correct target."""
    boot_file.write_text("# Check stuff\n")

    with mock.patch.object(boot_md_mod, "_get_boot_file", return_value=boot_file), \
         mock.patch.object(boot_md_mod, "threading") as mock_threading:
        mock_thread = mock.MagicMock()
        mock_threading.Thread.return_value = mock_thread

        boot_md_mod._on_session_start(session_id="test-session")

        call_kwargs = mock_threading.Thread.call_args
        assert call_kwargs.kwargs["daemon"] is True
        assert call_kwargs.kwargs["target"] == boot_md_mod._run_boot_agent
        assert call_kwargs.kwargs["args"] == ("# Check stuff",)


def test_session_start_only_runs_once(hermes_home, boot_file):
    """Second call to _on_session_start should be a no-op."""
    boot_file.write_text("# Startup\n")

    with mock.patch.object(boot_md_mod, "_get_boot_file", return_value=boot_file), \
         mock.patch.object(boot_md_mod, "threading") as mock_threading:
        mock_thread = mock.MagicMock()
        mock_threading.Thread.return_value = mock_thread

        boot_md_mod._on_session_start(session_id="session-1")
        boot_md_mod._on_session_start(session_id="session-2")

        # Only one thread should have been created
        assert mock_threading.Thread.call_count == 1


def test_run_boot_agent_calls_ai_agent():
    """_run_boot_agent spawns AIAgent and calls run_conversation."""
    mock_agent = mock.MagicMock()
    mock_agent.run_conversation.return_value = {"final_response": "[SILENT]"}

    with mock.patch.dict(
        "sys.modules",
        {"run_agent": mock.MagicMock(AIAgent=mock.MagicMock(return_value=mock_agent))},
    ):
        boot_md_mod._run_boot_agent("# Do stuff")

        mock_agent.run_conversation.assert_called_once()
        prompt_arg = mock_agent.run_conversation.call_args[0][0]
        assert "# Do stuff" in prompt_arg
        assert "BOOT.md" in prompt_arg


def test_build_boot_prompt():
    """_build_boot_prompt wraps content correctly."""
    prompt = boot_md_mod._build_boot_prompt("Check the logs")
    assert "Check the logs" in prompt
    assert "[SILENT]" in prompt
    assert "BOOT.md" in prompt


def test_register_hooks():
    """register() should register the on_session_start hook."""
    ctx = mock.MagicMock()
    boot_md_mod.register(ctx)
    ctx.register_hook.assert_called_once_with("on_session_start", boot_md_mod._on_session_start)
