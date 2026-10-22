"""异常数据的人工修复与重新生成。"""

from __future__ import annotations

import traceback
from datetime import date
from typing import Callable

from common.config import Settings
from common.errors import ErrorCode, error_label
from common.models import Packet, extract_abnormal_status, parse_report_text
from report.generator import generate_packet_documents
from utils.facility_index import FacilityIndex
from utils.file_utils import ErrorRecord, delete_file, save_error_packet
from utils.image_index import ImageIndex, normalize_image_name

LogFunc = Callable[..., None]


def regenerate_error_report(
    record: ErrorRecord,
    text: str,
    settings: Settings,
    facility_index: FacilityIndex,
    image_index: ImageIndex,
    log_func: LogFunc,
) -> bool:
    """
    用用户修改后的文本重新解析并生成报表。

    返回 True 表示已成功生成；False 表示仍有异常，数据已重新写回异常目录。
    """
    packet = record.packet
    day = packet.send_time.date() if packet.send_time else date.today()
    image_map = dict(image_index.refresh(day))
    # 已归档到 chat_logs/<群号>/image 的图片优先
    image_map.update(_archived_group_images(settings, packet))

    parsed = parse_report_text(text)
    facility = facility_index.lookup(parsed.town, parsed.village)

    error_codes: list[int] = []
    if not parsed.is_valid:
        error_codes.append(int(ErrorCode.TEXT_FORMAT))
    if facility is None:
        error_codes.append(int(ErrorCode.FACILITY_NOT_FOUND))

    packet.all_text = text
    packet.message = parsed.message
    packet.town_name = parsed.town
    packet.village_name = parsed.village
    packet.abnormal_status = extract_abnormal_status(parsed.message)

    if facility is None:
        packet.facility_code = ""
        packet.facility_name = ""
        packet.process = ""
    else:
        packet.facility_code = facility.code
        packet.facility_name = facility.name
        packet.process = facility.process

    packet.error_codes = error_codes
    packet.resolve_images(image_map)

    delete_file(record.path)

    if packet.error_codes:
        save_error_packet(settings.report_path, packet)
        log_func(
            f"{packet.town or '未知地点'} 仍存在异常: {error_label(packet.error_codes)}",
            "WARNING",
        )
        return False

    try:
        outputs = generate_packet_documents(packet, settings)
    except Exception:
        packet.add_error(0)
        save_error_packet(settings.report_path, packet)
        log_func(f"重新生成报表失败:\n{traceback.format_exc()}", "ERROR")
        return False

    log_func(f"异常数据已修复，报表已生成: {packet.town}", "SUCCESS")
    for output in outputs:
        log_func(f"  -> {output}")
    return True


def _archived_group_images(settings: Settings, packet: Packet) -> dict[str, str]:
    """索引 chat_logs/<群号>/image/ 下已归档的图片。"""
    group_id = str(packet.group_id or "")
    if not group_id:
        return {}

    image_dir = settings.project_root / "chat_logs" / group_id / "image"
    if not image_dir.is_dir():
        return {}

    return {
        normalize_image_name(path.name): str(path)
        for path in image_dir.iterdir()
        if path.is_file()
    }
