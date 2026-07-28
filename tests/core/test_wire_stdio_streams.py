"""Wire stdio：Linux 下 connect_write_pipe 返回 (transport, protocol)，必须正确解包。"""

from __future__ import annotations

import asyncio
import inspect
import os
import subprocess
import sys
import textwrap

import pytest

from kxns_cli.wire import server as server_mod


def test_stdio_streams_source_unpacks_write_pipe_tuple():
    src = inspect.getsource(server_mod._stdio_streams)
    assert "write_transport, write_protocol" in src
    # 禁止把整个元组当作 transport（旧 bug）
    assert "transport=await loop.connect_write_pipe" not in src


@pytest.mark.skipif(sys.platform == "win32", reason="Unix stdio pipes only")
def test_stdio_streams_subprocess_can_write_json_line():
    """子进程验证：修复后 stdout 能写出 JSON 行，不再 AttributeError。"""
    script = textwrap.dedent(
        """
        import asyncio
        from kxns_cli.wire.server import _stdio_streams

        async def main() -> None:
            _reader, writer = await _stdio_streams()
            assert not isinstance(writer.transport, tuple)
            writer.write(b'{"ok":true}\\n')
            await writer.drain()

        asyncio.run(main())
        """
    )
    env = {**os.environ, "PYTHONPATH": "src"}
    # 使用项目 venv 的 python
    proc = subprocess.run(
        [sys.executable, "-c", script],
        input=b"",
        capture_output=True,
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        env=env,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr.decode()
    assert b'{"ok":true}' in proc.stdout
    assert b"AttributeError" not in proc.stderr
