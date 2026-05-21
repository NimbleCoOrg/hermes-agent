"""Tests for swarm-map-policy plugin — HSM integration for group access control."""
import pytest
from unittest.mock import patch, MagicMock


class TestSwarmMapPolicy:

    def test_plugin_registers_hooks(self):
        """Plugin registers on_session_start and pre_tool_call hooks."""
        from plugins.swarm_map_policy import register
        ctx = MagicMock()
        register(ctx)
        hook_names = [call.args[0] for call in ctx.register_hook.call_args_list]
        assert "on_session_start" in hook_names
        assert "pre_tool_call" in hook_names

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
