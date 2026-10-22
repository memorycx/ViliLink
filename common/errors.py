"""统一的异常错误码与展示文本。"""

from __future__ import annotations

from enum import IntEnum
from typing import Any, Iterable


class ErrorCode(IntEnum):
    TEXT_FORMAT = 1
    IMAGE_MISSING = 2
    FACILITY_NOT_FOUND = 3


ERROR_LABELS: dict[int, str] = {
    0: "未知异常",
    1: "文本格式异常",
    2: "关联图片缺失/异常",
    3: "无法匹配设施编号",
}


def normalize_error_codes(raw: Any) -> list[int]:
    """兼容旧数据中的 str/int/list，去重并保持出现顺序。"""
    if raw is None:
        return []

    if isinstance(raw, (str, int, ErrorCode)):
        values: Iterable[Any] = [raw]
    else:
        values = raw

    result: list[int] = []
    for item in values:
        try:
            code = int(item)
        except (TypeError, ValueError):
            continue
        if code not in result:
            result.append(code)
    return result


def error_label(raw: Any) -> str:
    codes = normalize_error_codes(raw)
    if not codes:
        return "数据异常"
    return " | ".join(ERROR_LABELS.get(code, f"错误{code}") for code in codes)
