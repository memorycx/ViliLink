"""待维修消息的保存、通知、列表与完成处理。"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Callable, Mapping

from common.config import Settings
from common.models import RepairTask, parse_send_time
from repair.notifier import QQNotifier
from utils.file_utils import append_jsonl, read_jsonl
from utils.paths import safe_filename

LogFunc = Callable[..., None]


class RepairService:
    def __init__(self, settings: Settings, notifier: QQNotifier, log_func: LogFunc):
        self._settings = settings
        self._notifier = notifier
        self._log = log_func
        self._lock = threading.Lock()

    @property
    def repair_file(self) -> Path:
        return self._settings.report_path / "repair_message.jsonl"

    def handle(self, event: Mapping[str, Any]) -> None:
        """缓存维修消息并通知维修人员。由监听线程调用。"""
        with self._lock:
            append_jsonl(self.repair_file, dict(event))

        text = self._format_notification(event)
        if self._notifier.send_private(text):
            self._log("维修通知发送成功", "SUCCESS")
        else:
            self._log("维修通知发送失败，请手动联系", "WARNING")

    def list_tasks(self) -> list[RepairTask]:
        """返回去重后的待维修列表，每条记录对应 乡镇_自然村_日期。"""
        with self._lock:
            rows = read_jsonl(self.repair_file, strict=False)

        tasks: list[RepairTask] = []
        seen: set[tuple[str, str, str]] = set()
        for row in rows:
            task = self._task_from_row(row)
            if task is None or task.key in seen:
                continue
            seen.add(task.key)
            tasks.append(task)

        tasks.sort(key=lambda item: item.date, reverse=True)
        return tasks

    def complete(self, task: RepairTask) -> None:
        """删除待维修记录，并清理该地点当天的异常报表。"""
        with self._lock:
            self._remove_rows(task)
        self._remove_reports(task)

    def _remove_rows(self, task: RepairTask) -> None:
        path = self.repair_file
        if not path.is_file():
            return

        kept: list[str] = []
        with path.open("r", encoding="utf-8") as file:
            for line in file:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    kept.append(line)
                    continue

                row_task = self._task_from_row(row) if isinstance(row, dict) else None
                if row_task is not None and row_task.key == task.key:
                    continue
                kept.append(line)

        temp_path = path.with_suffix(path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as file:
            file.writelines(kept)
        os.replace(temp_path, path)

    def _remove_reports(self, task: RepairTask) -> None:
        # 兼容新旧两种目录命名：乡镇_自然村 / 乡镇 自然村
        legacy_name = safe_filename(f"{task.town} {task.village}", "未知地点")
        for folder_name in (task.filename, legacy_name):
            folder = self._settings.report_path / "异常" / folder_name
            if not folder.is_dir():
                continue
            for file in folder.iterdir():
                if file.is_file() and task.date in file.name:
                    try:
                        file.unlink()
                    except OSError as exc:
                        self._log(f"删除异常报表失败 {file}: {exc}", "WARNING")

    @staticmethod
    def _task_from_row(row: Mapping[str, Any]) -> RepairTask | None:
        parts = row.get("message") or []
        if not parts or parts[0].get("type") != "text":
            return None

        split = str(row.get("raw_message") or "").split("，")
        if len(split) < 2:
            return None

        send_time = parse_send_time(row.get("time"))
        if send_time is None:
            return None

        town = split[0].strip()
        village = split[1].strip()
        if not town or not village:
            return None
        return RepairTask(town=town, village=village, date=send_time.strftime("%Y-%m-%d"))

    @staticmethod
    def _format_notification(event: Mapping[str, Any]) -> str:
        sender = event.get("sender") or {}
        user_name = sender.get("card") or sender.get("nickname") or event.get("user_id", "")
        return (
            f"姓名：{user_name} \n"
            f"qq账号：{event.get('user_id', '')} \n"
            f"上报消息： {event.get('raw_message', '')}"
        )
