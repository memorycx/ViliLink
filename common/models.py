"""报表相关的数据模型。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping, Sequence

from common.errors import ErrorCode, normalize_error_codes
from utils.image_index import normalize_image_name
from utils.paths import safe_filename

if TYPE_CHECKING:
    from utils.facility_index import FacilityInfo

TIME_FORMAT = "%Y-%m-%d %H-%M-%S"
DISPLAY_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"
ABNORMAL_NONE = "暂无"


def parse_send_time(value: Any) -> datetime | None:
    """兼容 datetime、10/13 位时间戳和常见字符串格式。"""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return _from_timestamp(value)

    text = str(value).strip()
    for fmt in (TIME_FORMAT, DISPLAY_TIME_FORMAT, "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return _from_timestamp(text)


def _from_timestamp(value: Any) -> datetime | None:
    try:
        timestamp = float(value)
        if timestamp > 1e11:  # 13 位毫秒时间戳
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


@dataclass(frozen=True)
class ParsedReportText:
    town: str
    village: str
    message: str
    is_valid: bool


def parse_report_text(text: str | None) -> ParsedReportText:
    """解析“乡镇，自然村，情况说明”格式的群消息。"""
    parts = (text or "").split("，")
    if len(parts) < 3:
        return ParsedReportText("", "", "", False)
    return ParsedReportText(
        town=parts[0].strip(),
        village=parts[1].strip(),
        message="，".join(parts[2:]).strip(),
        is_valid=True,
    )


def extract_abnormal_status(message: str | None) -> str:
    if not message or "异常" not in message:
        return ABNORMAL_NONE
    return message.split("异常", 1)[1].strip().lstrip(":：").strip()


@dataclass
class ReportData:
    """生成 docx 所需的纯数据，供单条报表与合并报表共用。"""

    town: str = ""
    date: str = ""
    facility_name: str = ""
    inspector: str = ""
    process: str = ""
    facility_code: str = ""
    record: str = ""
    abnormal_status: str = ABNORMAL_NONE
    image_paths: list[str] = field(default_factory=list)


@dataclass
class Packet:
    """一条群消息解析后的完整报表数据。"""

    all_text: str = ""
    image_names: list[str] = field(default_factory=list)
    send_time: datetime | None = None
    user_name: str = ""
    group_id: str = ""
    message: str = ""
    town_name: str = ""
    village_name: str = ""
    facility_code: str = ""
    facility_name: str = ""
    process: str = ""
    image_paths: list[str] = field(default_factory=list)
    abnormal_status: str = ABNORMAL_NONE
    error_codes: list[int] = field(default_factory=list)
    image_map: Mapping[str, str] = field(default_factory=dict, repr=False, compare=False)

    @property
    def town(self) -> str:
        return f"{self.town_name} {self.village_name}".strip()

    @property
    def folder_name(self) -> str:
        """报表子目录名：乡镇_自然村。"""
        raw = f"{self.town_name}_{self.village_name}".strip("_")
        return safe_filename(raw, "未知地点")

    @property
    def has_error(self) -> bool:
        return bool(self.error_codes)

    def add_error(self, code: ErrorCode | int) -> None:
        value = int(code)
        if value not in self.error_codes:
            self.error_codes.append(value)

    def remove_error(self, code: ErrorCode | int) -> None:
        value = int(code)
        self.error_codes = [item for item in self.error_codes if item != value]

    def resolve_images(self, image_map: Mapping[str, str] | None) -> None:
        """
        根据文件名索引重新解析图片路径，并维护“图片缺失”错误码。

        兼容旧异常文件：旧版本可能只保存了 image_path，没有 image_name，
        此时用已保存路径的文件名继续查找；索引里找不到但原文件还在时直接复用。
        """
        self.image_map = image_map or {}
        previous_paths = list(self.image_paths)
        names = list(self.image_names)
        if not names and previous_paths:
            names = [Path(path).name for path in previous_paths]

        # 旧路径按规范化文件名建索引，避免缺图导致下标错位。
        previous_by_name: dict[str, str] = {}
        for raw_path in previous_paths:
            previous_by_name.setdefault(
                normalize_image_name(Path(raw_path).name),
                raw_path,
            )

        resolved: list[str] = []
        missing = False

        for name in names:
            key = normalize_image_name(str(name))
            path = self.image_map.get(key)
            if path is None:
                previous = previous_by_name.get(key)
                if previous and Path(previous).is_file():
                    path = previous

            if path is None:
                missing = True
            elif str(path) not in resolved:
                resolved.append(str(path))

        self.image_paths = resolved
        if missing:
            self.add_error(ErrorCode.IMAGE_MISSING)
        else:
            self.remove_error(ErrorCode.IMAGE_MISSING)

    def to_report_data(self) -> ReportData:
        date_text = self.send_time.strftime("%Y-%m-%d") if self.send_time else ""
        return ReportData(
            town=self.town,
            date=date_text,
            facility_name=self.facility_name,
            inspector=self.user_name,
            process=self.process,
            facility_code=self.facility_code,
            record=self.message,
            abnormal_status=self.abnormal_status,
            image_paths=list(self.image_paths),
        )

    def to_dict(self) -> dict[str, Any]:
        """序列化。image_map 只是运行时索引，不写入错误文件。"""
        return {
            "all_text": self.all_text,
            "image_names": list(self.image_names),
            "send_time": self.send_time.strftime(TIME_FORMAT) if self.send_time else "",
            "user_name": self.user_name,
            "group_id": self.group_id,
            "message": self.message,
            "town_name": self.town_name,
            "village_name": self.village_name,
            "facility_code": self.facility_code,
            "facility_name": self.facility_name,
            "process": self.process,
            "image_paths": list(self.image_paths),
            "abnormal_status": self.abnormal_status,
            "error_codes": list(self.error_codes),
        }

    def to_json(self, ensure_ascii: bool = False, indent: int | None = None) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Packet:
        """同时兼容旧版字段名（image_name/image_path/error_code 等）。"""
        image_names = _as_list(data.get("image_names", data.get("image_name")))
        image_paths = _as_list(data.get("image_paths", data.get("image_path")))
        raw_errors = data.get("error_codes", data.get("error_code"))
        message = str(data.get("message") or "")

        packet = cls(
            all_text=str(data.get("all_text") or ""),
            image_names=[str(item) for item in image_names],
            send_time=parse_send_time(data.get("send_time")),
            user_name=str(data.get("user_name") or ""),
            group_id=str(data.get("group_id") or ""),
            message=message,
            town_name=str(data.get("town_name") or ""),
            village_name=str(data.get("village_name") or ""),
            facility_code=str(data.get("facility_code") or ""),
            facility_name=str(data.get("facility_name") or ""),
            process=str(data.get("process") or ""),
            image_paths=[str(item) for item in image_paths],
            abnormal_status=str(data.get("abnormal_status") or extract_abnormal_status(message)),
        )
        packet.error_codes = normalize_error_codes(raw_errors)
        return packet

    @classmethod
    def from_json(cls, raw: str) -> Packet:
        return cls.from_dict(json.loads(raw))

    @classmethod
    def from_raw_message(
        cls,
        event: Mapping[str, Any],
        image_names: Sequence[str],
        facility: FacilityInfo | None,
        image_map: Mapping[str, str] | None,
    ) -> Packet:
        """把 NapCat 群消息事件转换为 Packet。"""
        message_parts = event.get("message") or []
        first = message_parts[0] if message_parts else {}
        text = str((first.get("data") or {}).get("text") or "")
        parsed = parse_report_text(text)
        sender = event.get("sender") or {}

        packet = cls(
            all_text=text,
            image_names=[str(item) for item in image_names],
            send_time=parse_send_time(event.get("time")),
            user_name=str(sender.get("card") or sender.get("nickname") or ""),
            group_id=str(event.get("group_id") or ""),
            message=parsed.message,
            town_name=parsed.town,
            village_name=parsed.village,
            abnormal_status=extract_abnormal_status(parsed.message),
        )

        if not parsed.is_valid:
            packet.add_error(ErrorCode.TEXT_FORMAT)

        if facility is None:
            packet.add_error(ErrorCode.FACILITY_NOT_FOUND)
        else:
            packet.facility_code = facility.code
            packet.facility_name = facility.name
            packet.process = facility.process

        packet.resolve_images(image_map)
        return packet

    def __str__(self) -> str:
        return self.to_json()


@dataclass(frozen=True)
class RepairTask:
    town: str
    village: str
    date: str

    @property
    def filename(self) -> str:
        return safe_filename(f"{self.town}_{self.village}", "未知地点")

    @property
    def key(self) -> tuple[str, str, str]:
        return self.town, self.village, self.date


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (str, bytes)):
        return [value]
    try:
        return list(value)
    except TypeError:
        return [value]
