"""Swarm Map Policy Plugin — HSM-backed group access control.

Integrates with Hermes Swarm Map (HSM) to enforce:
- Group allowlists: only groups registered in HSM can interact
- Admin checks: platform admin status from HSM settings
- Tool gating: (future) per-group tool restrictions

Configuration via environment variables:
- HSM_URL: URL of the HSM API (e.g., http://localhost:3002)
- HERMES_AGENT_NAME: Agent identifier in HSM (e.g., hermes-personal)

Security model:
- Group checks: FAIL-CLOSED (deny if HSM unreachable)
- Tool checks: FAIL-OPEN (allow if not configured)
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    requests = None


def _hsm_url() -> Optional[str]:
    """Get HSM API URL from environment."""
    return os.environ.get("HSM_URL") or None


def _harness_id() -> Optional[str]:
    """Get this agent's harness ID from environment."""
    return os.environ.get("HERMES_AGENT_NAME") or None


def is_group_allowed(group_id: str, platform: str) -> bool:
    """Check if a group is in the HSM allowlist. Fail-closed."""
    url = _hsm_url()
    harness = _harness_id()
    if not url or not harness:
        logger.warning("swarm-map-policy: HSM not configured, denying group")
        return False
    try:
        resp = requests.get(
            f"{url}/api/harnesses/{harness}/surfaces/{platform}/groups/{group_id}",
            timeout=5,
        )
        return resp.status_code == 200 and resp.json().get("allowed", False)
    except Exception as e:
        logger.warning("swarm-map-policy: HSM check failed (fail-closed): %s", e)
        return False


def is_tool_allowed(tool_name: str, group_id: str) -> bool:
    """Check if a tool is allowed for a group. Fail-open."""
    url = _hsm_url()
    if not url:
        return True
    return True  # Future: check HSM tool gating API


def is_platform_admin(user_id: str, platform: str) -> bool:
    """Check if a user is a platform admin via HSM. Fail-closed."""
    url = _hsm_url()
    harness = _harness_id()
    if not url or not harness:
        return False
    try:
        resp = requests.get(
            f"{url}/api/harnesses/{harness}/surfaces/{platform}/admins/{user_id}",
            timeout=5,
        )
        return resp.status_code == 200 and resp.json().get("is_admin", False)
    except Exception:
        return False


def _on_session_start(session_id: str = None, **kwargs) -> None:
    """Log session start. Future: cache admin status, validate group."""
    logger.debug("swarm-map-policy: session start %s", session_id)


def _pre_tool_call(tool_name: str = None, **kwargs) -> None:
    """Gate tool calls based on HSM policy. Returns None to allow."""
    return None


def register(ctx):
    """Register plugin hooks."""
    if not requests:
        logger.warning("swarm-map-policy: 'requests' not installed, plugin disabled")
        return
    ctx.register_hook("on_session_start", _on_session_start)
    ctx.register_hook("pre_tool_call", _pre_tool_call)
    logger.info("swarm-map-policy: registered (HSM_URL=%s)", _hsm_url() or "not set")
