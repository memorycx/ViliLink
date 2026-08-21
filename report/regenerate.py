import asyncio
import json
import os
from datetime import date

from common.Config import config
from common.Packet import Packet
from report.merge import report, generate_docx
from utils.pack_utils import PackUtils
from utils.file_utils import FileUtils

LOCAL_IMAGES_DIR = config.LOCAL_IMAGES_DIR


def fix_error(text, file_path):
    """
    修复错误文本
    :param text: 正确的文本
    :param file_path: 错误文件路径
    :return: 处理好的数据包
    """

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    end_data = []

    if not text:
        for item in data[1:]:
            end_data.append(item)
        return end_data

    for item in data[1:]:
        if item["is_text"]:
            item["raw_message"] = text
            end_data.append(item)
            break
        if data[0]["error_message"] == "图片异常":
            base_name, ext = os.path.splitext(item["image_path"])
            image_path = find_files_by_partial_name(LOCAL_IMAGES_DIR, base_name)
            if image_path:
                item["image_path"] = image_path
            else:
                return None
        end_data.append(item)

    return end_data


def find_error_package(file_id):
    """
    根据随机数字，找到错误包
    :param file_id: 随机数
    :return: 错误包的路径
    """

    file_path = config.REPORT_PATH / 'error_message'
    file_path.mkdir(exist_ok=True)
    return file_path / f"error_message_{file_id}.jsonl"


def re_generate_docx(data_id, text, log_func, packet_utils, day=None):
    """
    重新生成docx文件
    :param day:
    :param packet_utils:
    :param log_func:
    :param data_id: 错误包的随机数
    :param text: 正确的文本
    """

    if not day:
        day = date.today()
    packet_utils.get_day_file_map(day)

    # 将基本信息格式化出来
    error_code = []
    town_name, village_name, message = PackUtils.parse_message(text, error_code)
    facility_code, facility_name, process = PackUtils.find_facility_info(
        town_name, village_name
    )

    if not facility_code or not facility_name or not process:
        error_code.append("3")

    # 实例化一个Packet对象
    file_path = find_error_package(data_id)
    json_dict = FileUtils.load_jsonl_file(file_path)
    if json_dict:
        json_dict = json_dict[0]
    packet = Packet.from_dict(json_dict)

    packet.image_map = packet_utils.image_cache
    packet.image_path = []
    packet.find_image()

    file_path.unlink(missing_ok=True)

    if error_code:
        json_str = packet.to_dict()
        file_path = config.REPORT_PATH / 'error_message'
        file_path.mkdir(exist_ok=True)
        FileUtils.save_jsonl_file(file_path, json_str)

        log_func(f"{packet.town} 的 code为 ---> {packet.error_code} ")
        return False

    generate_docx(packet, log_func)
    return True


