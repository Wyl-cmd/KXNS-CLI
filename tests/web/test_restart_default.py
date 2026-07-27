"""改全局模型默认应重启会话。"""

from __future__ import annotations

from kxns_cli.web.api.config import UpdateGlobalConfigRequest


def test_update_global_config_restarts_by_default():
    fields = UpdateGlobalConfigRequest.model_fields
    assert fields["restart_running_sessions"].default is True
