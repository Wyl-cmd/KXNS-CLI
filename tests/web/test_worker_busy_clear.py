"""Web worker 异常后必须清 busy（对齐 kimi）。"""

from __future__ import annotations

import inspect

from kxns_cli.web.runner import process as process_mod


def test_read_loop_clears_inflight_on_unexpected_error():
    src = inspect.getsource(process_mod.SessionProcess._read_loop)
    assert "_in_flight_prompt_ids.clear()" in src
    assert 'reason="read_loop_error"' in src


def test_process_exit_clears_busy_before_broadcast():
    src = inspect.getsource(process_mod.SessionProcess._read_loop)
    # clear 应出现在 broadcast 之前（同一退出分支内）
    exit_idx = src.find("process_exit")
    assert exit_idx > 0
    before = src[:exit_idx]
    clear_idx = before.rfind("_in_flight_prompt_ids.clear()")
    broadcast_idx = before.rfind("_broadcast(")
    assert clear_idx > 0
    assert broadcast_idx > 0
    assert clear_idx < broadcast_idx
