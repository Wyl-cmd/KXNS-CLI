"""回归：Web Config API 响应字段须与前端 OpenAPI 一致。"""

from __future__ import annotations

from kxns_cli.web.api.config import UpdateApiConfigResponse, UpdateGlobalConfigResponse
from kxns_cli.wire.protocol import WIRE_PROTOCOL_VERSION


def test_update_global_config_response_uses_restarted_session_ids():
    fields = UpdateGlobalConfigResponse.model_fields
    assert "restarted_session_ids" in fields
    assert "restarted_sessions" not in fields


def test_update_api_config_response_uses_restarted_session_ids():
    fields = UpdateApiConfigResponse.model_fields
    assert "restarted_session_ids" in fields
    assert "restarted_sessions" not in fields


def test_wire_protocol_version_matches_frontend_constant():
    # 前端 useSessionStream.ts initialize 使用同一版本号
    assert WIRE_PROTOCOL_VERSION == "1.4"
