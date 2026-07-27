"""Wire set_model 须套环境变量覆盖。"""

from __future__ import annotations

import inspect

from kxns_cli.wire import server as server_mod


def test_handle_set_model_augments_env_vars():
    src = inspect.getsource(server_mod.WireServer._handle_set_model)
    assert "augment_provider_with_env_vars" in src
    assert "model_copy(deep=True)" in src
