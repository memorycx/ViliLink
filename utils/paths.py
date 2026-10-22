"""路径相关的通用工具。"""

from __future__ import annotations

import re
import threading
from datetime import datetime
from pathlib import Path

_MONTH_PATTERN = re.compile(r"20\d{2}-(0[1-9]|1[0-2])")
_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVE_LOCK = threading.Lock()


def apply_current_month(value: str | Path, now: datetime | None = None) -> Path:
    """
    把路径中的 YYYY-MM 替换为当前年月。

    每月 1 号照片目录仍指向上个月（月初的报表通常是上月数据的延续）。
    路径中没有年月时保持原样。
    """
    now = now or datetime.now()
    if now.day == 1:
        if now.month == 1:
            year, month = now.year - 1, 12
        else:
            year, month = now.year, now.month - 1
    else:
        year, month = now.year, now.month

    return Path(_MONTH_PATTERN.sub(f"{year}-{month:02d}", str(value)))


def safe_filename(value: str | None, fallback: str = "未命名") -> str:
    """把任意文本转换为 Windows 下可用的文件名。"""
    cleaned = _INVALID_FILENAME_CHARS.sub("_", str(value or "")).strip().strip(".")
    return cleaned or fallback


def unique_path(path: str | Path) -> Path:
    """文件已存在时依次尝试 name_2、name_3 …"""
    path = Path(path)
    if not path.exists():
        return path

    index = 2
    while True:
        candidate = path.parent / f"{path.stem}_{index}{path.suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def reserve_path(path: str | Path) -> Path:
    """
    原子地占用一个唯一路径（创建空文件）。

    并发生成报表时，先占位可以避免多个线程选到同一个文件名。
    """
    path = Path(path)
    with _RESERVE_LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        candidate = unique_path(path)
        candidate.touch(exist_ok=False)
        return candidate
