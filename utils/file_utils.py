"""JSON / JSONL 文件读写与异常数据存储。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from common.models import Packet

# 旧版聊天缓存里偶尔混入极短的控制行，读取时忽略。
MIN_JSON_LINE_LENGTH = 15


@dataclass(frozen=True)
class ErrorRecord:
    """一个异常数据文件及其解析结果。"""

    file_id: str
    path: Path
    packet: Packet


def read_jsonl(path: str | Path, strict: bool = True) -> list[dict[str, Any]]:
    """
    读取 JSONL 文件。

    strict=True 时遇到坏行直接抛错（聊天缓存需要暴露损坏）；
    strict=False 时跳过坏行（异常列表/维修列表需要尽量加载）。
    """
    path = Path(path)
    if not path.is_file():
        return []

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as file:
        for line_number, raw_line in enumerate(file, 1):
            line = raw_line.strip()
            if not line or len(line) <= MIN_JSON_LINE_LENGTH:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                if strict:
                    raise ValueError(f"JSON 解析失败: {path} 第 {line_number} 行") from exc
                continue
            if isinstance(item, dict):
                rows.append(item)
    return rows


def read_json(path: str | Path) -> Any:
    path = Path(path)
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: str | Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False)


def write_jsonl(path: str | Path, rows: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(path: str | Path, row: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(row, ensure_ascii=False) + "\n")


def delete_file(path: str | Path) -> None:
    Path(path).unlink(missing_ok=True)


def error_message_dir(report_root: str | Path) -> Path:
    return Path(report_root) / "error_message"


def save_error_packet(report_root: str | Path, packet: Packet) -> Path:
    """把生成失败的数据完整保存，文件名与旧版本保持兼容。"""
    directory = error_message_dir(report_root)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"error_message_{uuid4().hex}.jsonl"
    write_json(path, packet.to_dict())
    return path


def load_error_packets(report_root: str | Path) -> list[ErrorRecord]:
    """加载异常目录，单个坏文件不影响其他数据。"""
    directory = error_message_dir(report_root)
    if not directory.is_dir():
        return []

    records: list[ErrorRecord] = []
    for path in directory.iterdir():
        if not path.is_file() or path.name.startswith("."):
            continue
        try:
            packet = Packet.from_dict(read_json(path))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue

        file_id = path.stem
        if file_id.startswith("error_message_"):
            file_id = file_id[len("error_message_"):]
        records.append(ErrorRecord(file_id=file_id, path=path, packet=packet))

    records.sort(
        key=lambda record: (record.packet.send_time or datetime.min, record.file_id),
        reverse=True,
    )
    return records
