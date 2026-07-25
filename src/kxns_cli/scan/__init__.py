"""Scan orchestration domain."""

from kxns_cli.scan.models import ScanConfig, ScanMode, ScanRunResult

__all__ = ["ScanConfig", "ScanMode", "ScanRunResult", "ScanManager"]


def __getattr__(name: str):
    if name == "ScanManager":
        from kxns_cli.scan.manager import ScanManager

        return ScanManager
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
