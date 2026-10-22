"""按日期建立图片文件名索引。"""

from __future__ import annotations

import os
import threading
from datetime import date
from pathlib import Path
from typing import Callable, Mapping, Sequence

LogFunc = Callable[..., None]


def normalize_image_name(filename: str) -> str:
    """去掉 QQ 缓存追加的 _数字 后缀，并统一大小写。"""
    stem, extension = os.path.splitext(filename)
    stem = stem.lower()
    if "_" in stem:
        base, suffix = stem.rsplit("_", 1)
        if suffix.isdigit():
            stem = base
    return f"{stem}{extension.lower()}"


class ImageIndex:
    """
    扫描 QQ 图片目录，得到 {规范化文件名: 完整路径}。

    QQ 缓存会在文件名末尾追加 _数字，索引时统一去掉，便于消息中的原始文件名命中。
    """

    def __init__(
        self,
        directories: Sequence[str | Path] | None = None,
        log_func: LogFunc | None = None,
    ):
        self._directories = [Path(item) for item in (directories or [])]
        self._log = log_func
        self._mapping: dict[str, str] = {}
        self._loaded_day: date | None = None
        self._lock = threading.Lock()

    def set_directories(self, directories: Sequence[str | Path]) -> None:
        with self._lock:
            self._directories = [Path(item) for item in directories]
            self._mapping = {}
            self._loaded_day = None

    @property
    def mapping(self) -> Mapping[str, str]:
        with self._lock:
            return dict(self._mapping)

    @property
    def loaded_day(self) -> date | None:
        return self._loaded_day

    def refresh(self, day: date | None = None) -> Mapping[str, str]:
        target_day = day or date.today()
        with self._lock:
            directories = list(self._directories)

        mapping: dict[str, str] = {}
        for directory in directories:
            if not directory.is_dir():
                continue
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        try:
                            created = date.fromtimestamp(entry.stat().st_ctime)
                        except OSError:
                            continue
                        if created == target_day:
                            mapping[normalize_image_name(entry.name)] = entry.path
            except OSError as exc:
                self._warn(f"读取图片目录失败 {directory}: {exc}")

        with self._lock:
            self._mapping = mapping
            self._loaded_day = target_day

        if self._log is not None:
            self._log(f"图片索引完成（{target_day}）：共 {len(mapping)} 张")
        return self.mapping

    def _warn(self, message: str) -> None:
        if self._log is not None:
            self._log(message, "WARNING")
