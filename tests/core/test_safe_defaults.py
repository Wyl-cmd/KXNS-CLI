"""协作合并后的安全默认值：不强制 YOLO / 不劫持对话 / 不强制 PG。"""

from __future__ import annotations

import inspect

from kxns_cli.config import get_default_config
from kxns_cli.soul.agent import Runtime


def test_safe_scan_blackboard_defaults():
    config = get_default_config()
    assert config.scan.authorized_attack is False
    assert config.scan.auto_scan_on_hunt_intent is False
    assert config.blackboard is not None
    assert config.blackboard.backend == "memory"
    assert config.blackboard.require_postgres is False


def test_runtime_copy_preserves_blackboard_fields():
    """子 agent copy 必须透传 blackboard / scan_engagement_id。"""
    src_fixed = inspect.getsource(Runtime.copy_for_fixed_subagent)
    src_dyn = inspect.getsource(Runtime.copy_for_dynamic_subagent)
    assert "blackboard=self.blackboard" in src_fixed
    assert "scan_engagement_id=self.scan_engagement_id" in src_fixed
    assert "blackboard=self.blackboard" in src_dyn
    assert "scan_engagement_id=self.scan_engagement_id" in src_dyn
