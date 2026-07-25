"""Official Burp Suite MCP tool name mapping (PortSwigger extension)."""

from __future__ import annotations

BURP_OFFICIAL_MCP_TOOLS: frozenset[str] = frozenset(
    {
        "send_http_request",
        "send_http1_request",
        "send_http2_request",
        "create_repeater_tab",
        "send_to_repeater",
        "send_to_intruder",
        "send_to_organizer",
        "get_proxy_http_history",
        "get_proxy_http_history_regex",
        "get_scanner_issues",
        "generate_collaborator_payload",
        "poll_collaborator_interactions",
        "set_proxy_intercept_state",
        "set_task_execution_engine_state",
        "set_project_options",
        "output_project_options",
        "output_user_options",
        "set_user_options",
        "set_scope",
        "include_in_scope",
        "exclude_from_scope",
    }
)

BURP_ACTION_TOOL_CANDIDATES: dict[str, list[str]] = {
    "proxy_url": [
        "send_to_repeater",
        "create_repeater_tab",
        "send_http_request",
        "include_in_scope",
    ],
    "scan_passive": [
        "get_scanner_issues",
        "get_proxy_http_history",
        "send_http_request",
    ],
}
