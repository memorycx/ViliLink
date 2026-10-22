"""应用配置的加载、解析与持久化。"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv, set_key

from utils.paths import apply_current_month

DEFAULT_WS_BASE_URL = "ws://127.0.0.1:3001"
DEFAULT_URL_SEND = "http://127.0.0.1:6098/send_private_msg"


def _project_root() -> Path:
    """开发环境为仓库根目录；PyInstaller 打包后为 exe 所在目录。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _project_root()
_ENV_CANDIDATES = (PROJECT_ROOT / ".env", PROJECT_ROOT / "common" / ".env")


def _load_env_file() -> Path:
    """
    依次加载根目录 .env 和 common/.env（兼容旧版本）。

    override=False 保证先加载的文件优先，同时不覆盖系统环境变量。
    """
    loaded: Path | None = None
    for candidate in _ENV_CANDIDATES:
        if candidate.is_file():
            load_dotenv(dotenv_path=candidate, override=False)
            if loaded is None:
                loaded = candidate
    return loaded or _ENV_CANDIDATES[0]


ENV_FILE = _load_env_file()


def _env_text(key: str, default: str = "") -> str:
    value = os.getenv(key)
    return default if value is None else value.strip()


def _env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_path(key: str, default: Path) -> Path:
    value = _env_text(key)
    return Path(value) if value else default


def _env_float(key: str, default: float) -> float:
    value = _env_text(key)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def parse_image_dirs(raw: str | None) -> list[Path]:
    """解析逗号/换行分隔的图片目录，保持顺序并去重。"""
    result: list[Path] = []
    seen: set[str] = set()
    for part in re.split(r"[,\n]", raw or ""):
        text = part.strip().strip('"').strip("'").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(Path(text))
    return result


def _to_env_path(path: Path) -> str:
    # 统一使用正斜杠，避免 Windows 反斜杠被 dotenv 当作转义字符。
    return str(path).replace("\\", "/")


def _env_key_value(value: str | Path | bool | float) -> str:
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, Path):
        return _to_env_path(value)
    return str(value)


@dataclass
class Settings:
    project_root: Path
    env_file: Path
    token_websocket: str
    ws_base_url: str
    token_send: str
    url_send: str
    report_path: Path
    image_dirs: list[Path]
    auto_month_paths: bool
    facility_file: Path
    report_people_qq: str
    report_group: str
    request_timeout: float = 10.0

    @property
    def websocket_url(self) -> str:
        base = self.ws_base_url.rstrip("/")
        separator = "&" if "?" in base else "?"
        return f"{base}{separator}access_token={self.token_websocket}"

    @property
    def headers_send(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token_send}"}

    @property
    def resolved_image_dirs(self) -> list[Path]:
        """运行时图片目录；开启自动月份时把 YYYY-MM 替换为当前月份。"""
        if not self.auto_month_paths:
            return list(self.image_dirs)
        return [apply_current_month(path) for path in self.image_dirs]

    def update(self, env_key: str, raw_value: Any) -> None:
        """更新一个配置项，并同步写回 .env 文件。"""
        key = str(env_key).strip().upper()
        text = str(raw_value).strip()
        stored = text

        if key == "TOKEN_WEBSOCKET":
            self.token_websocket = text
        elif key == "WS_BASE_URL":
            self.ws_base_url = text or DEFAULT_WS_BASE_URL
            stored = self.ws_base_url
        elif key == "TOKEN_SEND":
            self.token_send = text
        elif key == "URL_SEND":
            self.url_send = text or DEFAULT_URL_SEND
            stored = self.url_send
        elif key == "REPORT_PATH":
            self.report_path = Path(text) if text else self.project_root / "报表"
            stored = _to_env_path(self.report_path)
        elif key == "LOCAL_IMAGES_DIR":
            self.image_dirs = parse_image_dirs(text)
            stored = ",".join(_to_env_path(path) for path in self.image_dirs)
        elif key == "FACILITY_FILE":
            self.facility_file = Path(text) if text else self.project_root / "编号集合.xlsx"
            stored = _to_env_path(self.facility_file)
            if not text:
                stored = ""
        elif key == "REPORT_PEOPLE_QQ":
            self.report_people_qq = text
        elif key == "REPORT_GROUP":
            self.report_group = text
        elif key == "REQUEST_TIMEOUT":
            self.request_timeout = float(text)
            stored = str(self.request_timeout)
        elif key == "AUTO_MONTH_PATHS":
            self.auto_month_paths = text.lower() in {"1", "true", "yes", "on"}
            stored = "True" if self.auto_month_paths else "False"
        else:
            raise KeyError(f"未知配置项: {env_key}")

        self._persist(key, _env_key_value(stored))

    def _persist(self, key: str, value: str) -> None:
        self.env_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.env_file.exists():
            self.env_file.touch()
        set_key(str(self.env_file), key, value)


def load_settings() -> Settings:
    return Settings(
        project_root=PROJECT_ROOT,
        env_file=ENV_FILE,
        token_websocket=_env_text("TOKEN_WEBSOCKET"),
        ws_base_url=_env_text("WS_BASE_URL", DEFAULT_WS_BASE_URL),
        token_send=_env_text("TOKEN_SEND"),
        url_send=_env_text("URL_SEND", DEFAULT_URL_SEND),
        report_path=_env_path("REPORT_PATH", PROJECT_ROOT / "报表"),
        image_dirs=parse_image_dirs(_env_text("LOCAL_IMAGES_DIR")),
        auto_month_paths=_env_bool("AUTO_MONTH_PATHS", True),
        facility_file=_env_path("FACILITY_FILE", PROJECT_ROOT / "编号集合.xlsx"),
        report_people_qq=_env_text("REPORT_PEOPLE_QQ"),
        report_group=_env_text("REPORT_GROUP"),
        request_timeout=_env_float("REQUEST_TIMEOUT", 10.0),
    )
