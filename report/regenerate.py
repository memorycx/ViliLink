import asyncio
import json

from config import config
from report.merge import report
from tool.tool import find_files_by_partial_name

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
            image_path = find_files_by_partial_name(LOCAL_IMAGES_DIR, item["image_path"])
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


def re_generate_docx(data_id, text, log_func):
    """
    重新生成docx文件
    :param log_func:
    :param data_id: 错误包的随机数
    :param text: 正确的文本
    """

    file_path = find_error_package(data_id)
    package = fix_error(text, file_path)

    if not package:
        log_func("修复数据失败，请重新修改错误包")
        return

    try:
        asyncio.run(report("", log_func, packages=package, is_dir=False))
    except Exception as e:
        log_func(f"重新生成docx文件失败: {e}")

    file_path.unlink(missing_ok=True)
