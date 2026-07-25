"""Finding validation — enforce no false positives in confirmed reports."""

from __future__ import annotations

from kxns_cli.scan.models import FindingSeverity, FindingStatus

MIN_DESCRIPTION_LEN = 20
MIN_POC_LEN_CONFIRMED = 15
MIN_POC_LEN_HIGH = 30


def validate_finding_submission(
    *,
    title: str,
    severity: FindingSeverity,
    description: str,
    poc: str,
    status: FindingStatus,
) -> tuple[bool, list[str]]:
    """Return (ok, errors). Candidates have relaxed rules; confirmed is strict."""
    errors: list[str] = []

    if not title.strip():
        errors.append("标题不能为空")
    if len(title.strip()) < 5:
        errors.append("标题过短，需清晰描述漏洞类型与位置")

    if not description.strip():
        errors.append("描述不能为空")
    elif len(description.strip()) < MIN_DESCRIPTION_LEN:
        errors.append(f"描述至少 {MIN_DESCRIPTION_LEN} 字符，需包含可验证证据")

    if status == FindingStatus.CONFIRMED:
        min_poc = (
            MIN_POC_LEN_HIGH
            if severity
            in (
                FindingSeverity.HIGH,
                FindingSeverity.CRITICAL,
            )
            else MIN_POC_LEN_CONFIRMED
        )
        if len(poc.strip()) < min_poc:
            errors.append(f"已确认漏洞必须提供可复现 POC（至少 {min_poc} 字符：curl/请求/步骤）")
        vague = ("maybe", "possible", "might", "疑似", "可能", "也许")
        combined = (description + poc).lower()
        if any(v in combined for v in vague) and severity in (
            FindingSeverity.HIGH,
            FindingSeverity.CRITICAL,
        ):
            errors.append("高危/严重已确认项不得使用模糊措辞；请用实际复现结果描述")

    if (
        status == FindingStatus.CONFIRMED
        and severity in (FindingSeverity.HIGH, FindingSeverity.CRITICAL)
        and not _looks_like_poc(poc)
    ):
        errors.append("高危/严重 POC 应包含可执行命令或 HTTP 请求（curl/http/参数）")

    return len(errors) == 0, errors


def _looks_like_poc(poc: str) -> bool:
    p = poc.lower()
    markers = ("curl", "http", "wget", "request", "payload", "参数", "步骤", "复现", "post", "get")
    return any(m in p for m in markers)


def parse_evaluate_confidence(text: str) -> float | None:
    """Parse CONFIDENCE: 0.85 from guaranteed evaluate job output."""
    for line in text.splitlines():
        line = line.strip()
        if line.upper().startswith("CONFIDENCE:"):
            try:
                return float(line.split(":", 1)[1].strip().split()[0])
            except (ValueError, IndexError):
                return None
    return None
