"""运行时资源定位（兼容源码运行与 PyInstaller 打包）。"""

from __future__ import annotations

import sys
from pathlib import Path


def resource_path(relative: str | Path) -> Path:
    """返回资源文件的绝对路径；PyInstaller 打包后资源位于 sys._MEIPASS 下。"""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative


ICON_PATH = resource_path("assets/icon.ico")
