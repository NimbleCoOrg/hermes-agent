"""Tests for swarm-map-policy plugin — HSM integration for group access control."""
import pytest
from unittest.mock import patch, MagicMock
from enum import Enum


def _make_event(platform="signal", chat_id="group-123", user_id="user-456"):
    """Create a mock MessageEvent with source attributes."""
    class MockPlatform(Enum):
        SIGNAL = "signal"
        TELEGRAM = "telegram"
        DISCORD = "discord"

    event = MagicMock()
    event.source.chat_id = chat_id
    event.source.user_id = user_id
    # Set platform as an enum with .value
    platform_enum = MockPlatform(platform) if platform in ("signal", "telegram", "discord") else MagicMock(value=platform)
    event.source.platform = platform_enum
    return event


class TestSwarmMapPolicy:

    def test_plugin_registers_hooks(self):
        """Plugin registers on_session_start, pre_tool_call, and pre_gateway_dispatch hooks."""
        from plugins.swarm_map_policy import register
        ctx = MagicMock()
        register(ctx)
        hook_names = [call.args[0] for call in ctx.register_hook.call_args_list]
        assert "on_session_start" in hook_names
        assert "pre_tool_call" in hook_names
        assert "pre_gateway_dispatch" in hook_names

    def test_hsm_url_from_env(self):
        from plugins.swarm_map_policy import _hsm_url
        with patch.dict("os.environ", {"HSM_URL": "http://localhost:3002"}):
            assert _hsm_url() == "http://localhost:3002"

    def test_hsm_url_missing_returns_none(self):
        from plugins.swarm_map_policy import _hsm_url
        with patch.dict("os.environ", {}, clear=True):
            assert _hsm_url() is None

    def test_group_check_fail_closed_on_error(self):
        from plugins.swarm_map_policy import is_group_allowed
        with patch("plugins.swarm_map_policy._hsm_url", return_value="http://dead:9999"):
            with patch("plugins.swarm_map_policy.requests") as mock_req:
                mock_req.get.side_effect = Exception("Connection refused")
                assert is_group_allowed("group-123", "signal") is False

    def test_group_check_fail_closed_no_config(self):
        from plugins.swarm_map_policy import is_group_allowed
        with patch("plugins.swarm_map_policy._hsm_url", return_value=None):
            assert is_group_allowed("group-123", "signal") is False

    def test_tool_check_fail_open(self):
        from plugins.swarm_map_policy import is_tool_allowed
        with patch("plugins.swarm_map_policy._hsm_url", return_value=None):
            assert is_tool_allowed("dangerous_tool", "group-123") is True

    def test_admin_check_fail_closed(self):
        from plugins.swarm_map_policy import is_platform_admin
        with patch("plugins.swarm_map_policy._hsm_url", return_value=None):
            assert is_platform_admin("user-123", "signal") is False


class TestSessionContextCaching:
    """Tests for session context caching via pre_gateway_dispatch."""

    def setup_method(self):
        """Clear session context before each test."""
        from plugins.swarm_map_policy import clear_session_context
        clear_session_context()

    def test_pre_gateway_dispatch_caches_context(self):
        """pre_gateway_dispatch extracts and caches platform/chat_id/user_id."""
        from plugins.swarm_map_policy import _pre_gateway_dispatch, get_session_context
        event = _make_event(platform="signal", chat_id="group-123", user_id="user-456")
        with patch("plugins.swarm_map_policy.is_platform_admin", return_value=False):
            result = _pre_gateway_dispatch(event=event)
        assert result is None  # Should allow normal dispatch
        ctx = get_session_context()
        assert ctx is not None
        assert ctx["platform"] == "signal"
        assert ctx["chat_id"] == "group-123"
        assert ctx["user_id"] == "user-456"

    def test_pre_gateway_dispatch_returns_none_on_no_event(self):
        """pre_gateway_dispatch returns None when no event provided."""
        from plugins.swarm_map_policy import _pre_gateway_dispatch, get_session_context
        result = _pre_gateway_dispatch(event=None)
        assert result is None
        assert get_session_context() is None

    def test_get_session_context_none_before_dispatch(self):
        """get_session_context returns None before any dispatch."""
        from plugins.swarm_map_policy import get_session_context
        assert get_session_context() is None

    def test_clear_session_context_resets(self):
        """clear_session_context removes cached data."""
        from plugins.swarm_map_policy import (
            _pre_gateway_dispatch, get_session_context, clear_session_context
        )
        event = _make_event()
        with patch("plugins.swarm_map_policy.is_platform_admin", return_value=False):
            _pre_gateway_dispatch(event=event)
        assert get_session_context() is not None
        clear_session_context()
        assert get_session_context() is None

    def test_pre_gateway_dispatch_handles_none_source_fields(self):
        """Gracefully handles None platform/chat_id/user_id."""
        from plugins.swarm_map_policy import _pre_gateway_dispatch, get_session_context
        event = MagicMock()
        event.source.platform = None
        event.source.chat_id = None
        event.source.user_id = None
        with patch("plugins.swarm_map_policy.is_platform_admin", return_value=False):
            result = _pre_gateway_dispatch(event=event)
        assert result is None
        ctx = get_session_context()
        assert ctx["platform"] == ""
        assert ctx["chat_id"] == ""
        assert ctx["user_id"] == ""


class TestAdminResolution:
    """Tests for admin identity resolution during pre_gateway_dispatch."""

    def setup_method(self):
        from plugins.swarm_map_policy import clear_session_context
        clear_session_context()

    def test_admin_resolved_on_dispatch(self):
        """Admin status is resolved and cached during pre_gateway_dispatch."""
        from plugins.swarm_map_policy import _pre_gateway_dispatch, get_session_context
        event = _make_event(platform="signal", user_id="admin-user")
        with patch("plugins.swarm_map_policy.is_platform_admin", return_value=True):
            _pre_gateway_dispatch(event=event)
        ctx = get_session_context()
        assert ctx["is_admin"] is True

    def test_non_admin_resolved_on_dispatch(self):
        """Non-admin status is correctly cached."""
        from plugins.swarm_map_policy import _pre_gateway_dispatch, get_session_context
        event = _make_event(platform="signal", user_id="regular-user")
        with patch("plugins.swarm_map_policy.is_platform_admin", return_value=False):
            _pre_gateway_dispatch(event=event)
        ctx = get_session_context()
        assert ctx["is_admin"] is False

    def test_admin_resolution_fail_closed(self):
        """Admin resolution defaults to False on HSM failure."""
        from plugins.swarm_map_policy import _pre_gateway_dispatch, get_session_context
        event = _make_event(platform="signal", user_id="user-123")
        with patch("plugins.swarm_map_policy.is_platform_admin", side_effect=Exception("HSM down")):
            _pre_gateway_dispatch(event=event)
        ctx = get_session_context()
        assert ctx["is_admin"] is False

    def test_admin_resolution_called_with_correct_args(self):
        """is_platform_admin called with user_id and platform from event."""
        from plugins.swarm_map_policy import _pre_gateway_dispatch
        event = _make_event(platform="telegram", user_id="tg-user-789")
        with patch("plugins.swarm_map_policy.is_platform_admin", return_value=False) as mock_admin:
            _pre_gateway_dispatch(event=event)
        mock_admin.assert_called_once_with("tg-user-789", "telegram")


class TestApprovalGating:
    """Tests for approval command admin gating via pre_tool_call."""

    def setup_method(self):
        from plugins.swarm_map_policy import clear_session_context
        clear_session_context()

    def _set_admin_context(self, is_admin=True):
        """Set up session context with admin status."""
        from plugins.swarm_map_policy import _pre_gateway_dispatch
        event = _make_event(platform="signal", user_id="user-1")
        with patch("plugins.swarm_map_policy.is_platform_admin", return_value=is_admin):
            _pre_gateway_dispatch(event=event)

    def test_admin_can_use_approval_tool(self):
        """Admin users can execute approval tools."""
        from plugins.swarm_map_policy import _pre_tool_call
        self._set_admin_context(is_admin=True)
        result = _pre_tool_call(tool_name="approval")
        assert result is None  # Allowed

    def test_non_admin_blocked_from_approval(self):
        """Non-admin users are blocked from approval tools."""
        from plugins.swarm_map_policy import _pre_tool_call
        self._set_admin_context(is_admin=False)
        result = _pre_tool_call(tool_name="approval")
        assert result is not None
        assert result["action"] == "block"
        assert "admin" in result["message"].lower() or "Admin" in result["message"]

    def test_non_admin_blocked_from_pr_approval(self):
        """Non-admin users are blocked from pr_approval tool."""
        from plugins.swarm_map_policy import _pre_tool_call
        self._set_admin_context(is_admin=False)
        result = _pre_tool_call(tool_name="pr_approval")
        assert result is not None
        assert result["action"] == "block"

    def test_no_context_blocks_approval(self):
        """Missing session context blocks approval tools (fail-closed)."""
        from plugins.swarm_map_policy import _pre_tool_call
        # No dispatch happened, so no context
        result = _pre_tool_call(tool_name="approval")
        assert result is not None
        assert result["action"] == "block"

    def test_non_gated_tool_allowed_without_admin(self):
        """Non-gated tools are allowed regardless of admin status."""
        from plugins.swarm_map_policy import _pre_tool_call
        self._set_admin_context(is_admin=False)
        result = _pre_tool_call(tool_name="web_search")
        assert result is None  # Allowed

    def test_non_gated_tool_allowed_without_context(self):
        """Non-gated tools are allowed even without session context."""
        from plugins.swarm_map_policy import _pre_tool_call
        result = _pre_tool_call(tool_name="web_search")
        assert result is None  # Allowed
