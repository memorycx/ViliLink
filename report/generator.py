"""从聊天缓存批量生成报表。"""

from __future__ import annotations

import shutil
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from common.config import Settings
from common.errors import error_label
from common.models import ABNORMAL_NONE, Packet, parse_report_text
from utils.docx_utils import DEFAULT_REPORT_TITLE, generate_report
from utils.facility_index import FacilityIndex
from utils.file_utils import read_jsonl, save_error_packet
from utils.image_index import ImageIndex, normalize_image_name
from utils.paths import reserve_path, safe_filename

ABNORMAL_TITLE = "农村生活污水设施异常记录表"
REPAIR_TITLE = "农村生活污水设施维修记录表"
MAX_WORKERS = 4

LogFunc = Callable[..., None]


class ReportGenerator:
    def __init__(
        self,
        settings: Settings,
        facility_index: FacilityIndex,
        image_index: ImageIndex,
        log_func: LogFunc,
    ):
        self._settings = settings
        self._facility_index = facility_index
        self._image_index = image_index
        self._log = log_func
        # 本次生成中已经归档过的图片：规范化文件名 -> 本地路径
        self._relocated_images: dict[str, str] = {}

    def generate_for_day(self, day: date | None = None) -> int:
        """生成指定日期（默认今天）的全部报表，返回成功生成的报表文件数。"""
        target_day = day or date.today()
        self._relocated_images = {}
        self._image_index.refresh(target_day)

        chat_root = self._settings.project_root / "chat_logs"
        if not chat_root.is_dir():
            self._log(f"未找到聊天缓存目录: {chat_root}", "WARNING")
            return 0

        day_text = target_day.strftime("%Y-%m-%d")
        generated = 0

        for group_dir in sorted(path for path in chat_root.iterdir() if path.is_dir()):
            group_packets: list[Packet] = []

            for log_file in sorted(group_dir.glob("*.jsonl")):
                if day_text not in log_file.name:
                    continue
                try:
                    messages = read_jsonl(log_file)
                except (OSError, ValueError) as exc:
                    self._log(f"读取 {log_file.name} 失败: {exc}", "ERROR")
                    continue

                packets = self._build_packets(messages, group_dir)
                group_packets.extend(packets)
                self._log(f"正在处理 {log_file.name}，解析出 {len(packets)} 条报表")

            if group_packets:
                generated += self._generate_packets(group_packets)
                self._log(f"群 {group_dir.name} 的报表处理完毕")

        self._log(f"全部合成完毕，本次共生成 {generated} 份报表", "SUCCESS")
        return generated

    def _build_packets(
        self,
        messages: Sequence[Mapping[str, Any]],
        group_dir: Path,
    ) -> list[Packet]:
        qq_image_map = self._image_index.mapping
        image_dir = group_dir / "image"
        local_image_map = _index_local_images(image_dir)

        image_names: list[str] = []
        packets: list[Packet] = []
        moved_count = 0
        failed_count = 0

        for event in messages:
            parts = event.get("message") or []
            if not parts:
                continue

            first = parts[0]
            message_type = first.get("type")

            if message_type == "image":
                name = (first.get("data") or {}).get("file")
                if name:
                    image_names.append(str(name))
                continue

            if message_type != "text":
                continue

            moved, failed = self._relocate_images(
                image_names,
                image_dir,
                local_image_map,
                qq_image_map,
            )
            moved_count += moved
            failed_count += failed

            # 本地已归档的图片优先于 QQ 缓存路径
            image_map = dict(qq_image_map)
            image_map.update(local_image_map)

            text = str((first.get("data") or {}).get("text") or "")
            parsed = parse_report_text(text)
            facility = self._facility_index.lookup(parsed.town, parsed.village)

            packets.append(
                Packet.from_raw_message(
                    event=event,
                    image_names=image_names,
                    facility=facility,
                    image_map=image_map,
                )
            )
            image_names = []

        if moved_count or failed_count:
            message = f"群 {group_dir.name}: 已归档 {moved_count} 张图片到 {image_dir}"
            if failed_count:
                message += f"，{failed_count} 张移动失败"
            self._log(message, "WARNING" if failed_count else "INFO")

        return packets

    def _relocate_images(
        self,
        image_names: Sequence[str],
        image_dir: Path,
        local_map: dict[str, str],
        qq_map: Mapping[str, str],
    ) -> tuple[int, int]:
        """把 QQ 缓存中的图片移动到 chat_logs/<群号>/image/，返回（移动数，失败数）。"""
        moved = 0
        failed = 0

        for raw_name in image_names:
            key = normalize_image_name(str(raw_name))
            if key in local_map:
                continue

            source_text = qq_map.get(key)
            source = Path(source_text) if source_text else None

            if source is None or not source.is_file():
                # 同一张图可能已被本次运行归档到其他群目录（例如被转发）
                archived = self._relocated_images.get(key)
                if archived is None or not Path(archived).is_file():
                    continue
                image_dir.mkdir(parents=True, exist_ok=True)
                destination = image_dir / Path(archived).name
                try:
                    if not destination.exists():
                        shutil.copy2(archived, destination)
                except OSError as exc:
                    failed += 1
                    self._log(f"复制已归档图片失败 {Path(archived).name}: {exc}", "WARNING")
                    local_map[key] = archived
                else:
                    moved += 1
                    local_map[key] = str(destination)
                    self._relocated_images[key] = str(destination)
                continue

            image_dir.mkdir(parents=True, exist_ok=True)
            destination = image_dir / source.name
            if destination.exists():
                local_map[key] = str(destination)
                self._relocated_images.setdefault(key, str(destination))
                continue

            try:
                shutil.move(str(source), str(destination))
            except OSError as exc:
                failed += 1
                self._log(f"移动图片失败 {source}: {exc}", "WARNING")
                # 移动失败时保留原路径，报表仍可正常生成
                local_map[key] = str(source)
            else:
                moved += 1
                local_map[key] = str(destination)
                self._relocated_images[key] = str(destination)

        return moved, failed

    def _generate_packets(self, packets: list[Packet]) -> int:
        valid: list[Packet] = []
        for packet in packets:
            if packet.error_codes:
                save_error_packet(self._settings.report_path, packet)
                self._log(
                    f"{packet.town or '未知地点'} 数据异常: {error_label(packet.error_codes)}",
                    "WARNING",
                )
            else:
                valid.append(packet)

        if not valid:
            return 0

        success = 0
        workers = min(MAX_WORKERS, len(valid))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="report") as executor:
            futures = {
                executor.submit(generate_packet_documents, packet, self._settings): packet
                for packet in valid
            }
            for future in as_completed(futures):
                packet = futures[future]
                try:
                    outputs = future.result()
                except Exception:
                    packet.add_error(0)
                    save_error_packet(self._settings.report_path, packet)
                    self._log(
                        f"报表生成失败: {packet.town or '未知地点'} / {packet.user_name}\n"
                        f"{traceback.format_exc()}",
                        "ERROR",
                    )
                else:
                    success += len(outputs)
                    self._log(
                        f"报表生成成功: {packet.town or '未知地点'} / {packet.user_name}",
                        "SUCCESS",
                    )
        return success


def _index_local_images(image_dir: Path) -> dict[str, str]:
    if not image_dir.is_dir():
        return {}
    return {
        normalize_image_name(path.name): str(path)
        for path in image_dir.iterdir()
        if path.is_file()
    }


def generate_packet_documents(packet: Packet, settings: Settings) -> list[Path]:
    """生成一条 Packet 对应的运维/异常/维修报表。"""
    report_root = settings.report_path
    stamp = packet.send_time or datetime.now()
    date_text = stamp.strftime("%Y-%m-%d")
    time_text = stamp.strftime("%Y-%m-%d %H-%M-%S")
    user_name = safe_filename(packet.user_name, "未知人员")
    folder = packet.folder_name
    outputs: list[Path] = []

    # 维修优先级最高：正文包含“维修”时只生成维修报表，
    # 即使同时出现“异常”，也不再生成异常报表。
    has_repair_word = "维修" in (packet.message or "")
    is_repair = str(packet.group_id) == settings.report_group or has_repair_word

    if is_repair:
        outputs.append(
            _render(
                report_root / "维修" / folder / f"{user_name}_{date_text}.docx",
                packet,
                REPAIR_TITLE,
            )
        )
    else:
        outputs.append(
            _render(
                report_root / "运维" / folder / f"{time_text}_{user_name}.docx",
                packet,
                DEFAULT_REPORT_TITLE,
            )
        )

    if packet.abnormal_status != ABNORMAL_NONE and not has_repair_word:
        outputs.append(
            _render(
                report_root / "异常" / folder / f"{user_name}_{date_text}.docx",
                packet,
                ABNORMAL_TITLE,
            )
        )

    return outputs


def _render(path: Path, packet: Packet, title: str) -> Path:
    output_path = reserve_path(path)
    try:
        generate_report(output_path, packet.to_report_data(), title=title)
    except Exception:
        output_path.unlink(missing_ok=True)
        raise
    return output_path
