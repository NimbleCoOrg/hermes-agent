"""Tests for the boot_md builtin hook."""

import tempfile
import threading
from pathlib import Path
from unittest import mock

import pytest


@pytest.fixture
def hermes_home(tmp_path):
    """Provide a temporary HERMES_HOME directory."""
    return tmp_path


@pytest.fixture
def boot_file(hermes_home):
    """Return the path where BOOT.md would live."""
    return hermes_home / "BOOT.md"


def _import_boot_md(hermes_home):
    """Import boot_md with get_hermes_home patched to return hermes_home."""
    with mock.patch("hermes_cli.config.get_hermes_home", return_value=hermes_home):
        import importlib
        import gateway.builtin_hooks.boot_md as mod
        importlib.reload(mod)
        return mod


@pytest.mark.asyncio
async def test_boot_md_runs_on_startup(hermes_home, boot_file):
    """BOOT.md exists with content -> AIAgent.run_conversation is called."""
    boot_file.write_text("# Startup\n1. Check logs\n")

    mod = _import_boot_md(hermes_home)

    with mock.patch.object(mod, "threading") as mock_threading:
        mock_thread = mock.MagicMock()
        mock_threading.Thread.return_value = mock_thread

        await mod.handle("gateway:startup", {})

        mock_threading.Thread.assert_called_once()
        call_kwargs = mock_threading.Thread.call_args
        assert call_kwargs.kwargs["daemon"] is True
        assert call_kwargs.kwargs["name"] == "boot-md"
        mock_thread.start.assert_called_once()


@pytest.mark.asyncio
async def test_boot_md_skips_if_no_file(hermes_home):
    """No BOOT.md -> AIAgent is never instantiated."""
    mod = _import_boot_md(hermes_home)

    with mock.patch.object(mod, "threading") as mock_threading:
        await mod.handle("gateway:startup", {})
        mock_threading.Thread.assert_not_called()


@pytest.mark.asyncio
async def test_boot_md_skips_if_empty(hermes_home, boot_file):
    """BOOT.md exists but is empty -> AIAgent is never called."""
    boot_file.write_text("   \n  \n")

    mod = _import_boot_md(hermes_home)

    with mock.patch.object(mod, "threading") as mock_threading:
        await mod.handle("gateway:startup", {})
        mock_threading.Thread.assert_not_called()


@pytest.mark.asyncio
async def test_boot_md_runs_in_background_thread(hermes_home, boot_file):
    """Verify threading.Thread is used with daemon=True."""
    boot_file.write_text("# Check stuff\n")

    mod = _import_boot_md(hermes_home)

    with mock.patch.object(mod, "threading") as mock_threading:
        mock_thread = mock.MagicMock()
        mock_threading.Thread.return_value = mock_thread

        await mod.handle("gateway:startup", {})

        call_kwargs = mock_threading.Thread.call_args
        assert call_kwargs.kwargs["daemon"] is True
        assert call_kwargs.kwargs["target"] == mod._run_boot_agent
        assert call_kwargs.kwargs["args"] == ("# Check stuff",)


def test_run_boot_agent_calls_ai_agent(hermes_home, boot_file):
    """_run_boot_agent spawns AIAgent and calls run_conversation."""
    mod = _import_boot_md(hermes_home)

    mock_agent = mock.MagicMock()
    mock_agent.run_conversation.return_value = {"final_response": "[SILENT]"}

    with mock.patch("gateway.builtin_hooks.boot_md.AIAgent", create=True) as MockAgent:
        # We need to patch the import inside _run_boot_agent
        with mock.patch.dict("sys.modules", {"run_agent": mock.MagicMock(AIAgent=mock.MagicMock(return_value=mock_agent))}):
            mod._run_boot_agent("# Do stuff")

            # Verify run_conversation was called with the built prompt
            mock_agent.run_conversation.assert_called_once()
            prompt_arg = mock_agent.run_conversation.call_args[0][0]
            assert "# Do stuff" in prompt_arg
            assert "BOOT.md" in prompt_arg


def test_build_boot_prompt(hermes_home):
    """_build_boot_prompt wraps content correctly."""
    mod = _import_boot_md(hermes_home)
    prompt = mod._build_boot_prompt("Check the logs")
    assert "Check the logs" in prompt
    assert "[SILENT]" in prompt
    assert "BOOT.md" in prompt
