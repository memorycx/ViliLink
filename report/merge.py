import os
import re
import shutil
from datetime import date, datetime
from config import config, BASE_DIR
from report.error import error_report_save
from report.generate_docx_report import generate_docx_report
from tool.tool import find_files_by_partial_name, find_facility_info, load_jsonl_file, check_duplicate_file_names, \
    save_exception_to_jsonl

LOCAL_IMAGES_DIR = config.LOCAL_IMAGES_DIR


def keep_last_n_lines_jsonl(file_path, keep_lines=10):
    """
    只保留 JSONL 文件最后 N 行，删除前面的行
    :param file_path: JSONL 文件路径
    :param keep_lines: 要保留的最后行数
    """
    # 1. 读取所有行
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 2. 只保留最后 N 行
    if len(lines) > keep_lines:
        lines = lines[-keep_lines:]

    # 3. 覆盖写回原文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)


def package_message(message):
    """
    将消息处理好，处理好的数据最后一个应该是文本,
    如果最后一个不是文本消息，那么上一级就将该数据写入jsonl中
    :param message:
    :return:
    """
    package = []
    package_item = []

    if not message:
        return None

    index = 0

    while index < len(message):
        item = message[index]

        is_a_package = False

        while index < len(message) and message[index]["message"][0]["type"] == "text":
            item = message[index]
            index += 1

            sender_card = item["sender"].get("card")
            if not sender_card:
                sender_card = item["sender"]["nickname"]

            package_item.append({
                "raw_message": item["raw_message"],
                "nickname": sender_card,
                "group_id": item["group_id"],
                "time": datetime.fromtimestamp(item['time']).strftime('%Y-%m-%d %H:%M:%S'),
                "is_text": 1
            })
            is_a_package = True

        if is_a_package:
            package.append(package_item.copy())
            package_item.clear()

        if item["message"][0]["type"] == "image":
            image_name = item["message"][0]["data"]["file"]
            base_name, ext = os.path.splitext(image_name)
            image_path = find_files_by_partial_name(LOCAL_IMAGES_DIR, base_name)

            if not image_path:
                image_path = image_name

            package_item.append({
                'image_path': image_path,
                "group_id": item["group_id"],
                "time": datetime.fromtimestamp(item['time']).strftime('%Y-%m-%d'),
                "is_text": 0
            })

        index += 1

    return package


def merge_text_and_image(dir_name):
    today = date.today().strftime("%Y-%m-%d")
    message = []
    for file in os.listdir(dir_name):
        if today in file:
            message.extend(load_jsonl_file(os.path.join(dir_name, file)))

    return package_message(message)


def parse_abnormal(message):
    if "异常" in message:
        return message.split("异常", 1)[1].strip()  # strip() 去掉前后空格

    return "暂无"


def parse_address(address):
    """
    解析 xx镇xx村 格式地址
    返回：镇名、村名
    """
    if not address:
        return None, None

    # 正则匹配：【任意字符 + 镇】 + 【任意字符 + 村】
    pattern = r'(.+镇)(.+村)'
    match = re.match(pattern, address)

    if match:
        town = match.group(1).strip()  # 镇
        village = match.group(2).strip()  # 村
        return town, village
    return None, None


def prepare_data(target_path, is_dir=True):
    packages = []

    if not os.path.exists(target_path):
        return

    if is_dir:
        for file in os.listdir(target_path):
            dir_need = target_path / file
            packages = merge_text_and_image(dir_need)

            if not packages:
                continue

            for package in packages:
                if package[-1]['is_text'] == 0:
                    keep_last_n_lines_jsonl(os.path.join(target_path, file), len(package))
                    packages.remove(package)

    else:
        packages = load_jsonl_file(target_path)
        if packages[-1]['is_text'] == 0:
            keep_last_n_lines_jsonl(target_path, len(packages))
            packages.pop(packages)

    return packages


def has_error_message(package, data, group_id):
    if not data or not group_id:
        error_report_save(package, "编号异常")
        return True

    tem_text = 0
    tem_image = 0

    for item in package:
        if item["is_text"] == 1:
            tem_text += 1

        elif item["is_text"] == 0 and not os.path.isfile(item["image_path"]):
            tem_image += 1

    if tem_image > 0:
        error_report_save(package, "图片异常")
        return True

    if tem_text > 1:
        error_report_save(package, "多条文本")
        return True

    return False


def report_data(package):
    if package[-1]['is_text'] == 1:

        tem = package[-1]["raw_message"].split("，")

        if len(tem) < 3:
            error_report_save(package, "村镇异常")
            return None, None

        town, village = tem[0], tem[1]
        today = str(date.today())
        user = package[-1]["nickname"]
        message = ",".join(tem[2:])
        device_code, work = find_facility_info(town, village)
        abnormal = parse_abnormal(message)

        group_id = package[-1]["group_id"]

        if not device_code or not work:
            error_report_save(package, "编号异常")
            return None, None

        if "异常" in message:
            message = message.split("异常")[0]

        data = {
            "town": town,
            "date": f"{today}",
            "facility_name": village,
            "inspector": user,
            "process": work,
            "facility_code": device_code,
            "record": message,
            "abnormal_status": abnormal,
            "user": user,
        }

        return data, group_id


def generate_docx(data, package, group_id, log_func):
    report_path = config.REPORT_PATH / "运维" / f'{data["town"]}_{data["facility_name"]}' / (
        f'{str(data["date"])[:10]}_'
        f'{data["user"]}.docx')

    report_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        report_path = check_duplicate_file_names(report_path)

        generate_docx_report(
            report_path,
            data,
            package[:-1]
        )

        if data["abnormal_status"] != "暂无":
            report_path = config.REPORT_PATH / "异常" / f'{data["town"]}_{data["facility_name"]}' / f'{str(data["date"])[:10]}_{data["user"]}.docx'
            report_path = check_duplicate_file_names(report_path)
            generate_docx_report(
                report_path,
                data,
                package[:-1],
                t="农村生活污水设施异常记录表"
            )

        if str(group_id) == config.REPORT_GROUP:
            report_path = config.REPORT_PATH / "维修" / f'{data["town"]}_{data["facility_name"]}' / f'{str(data["date"])[:10]}_{data["user"]}.docx'
            report_path = check_duplicate_file_names(report_path)
            generate_docx_report(
                report_path,
                data,
                package[:-1],
                t="农村生活污水设施维修记录表"
            )

    except Exception as e:
        log_func(f"报表生成失败，详情请到报告目录下的异常文件中查看")

        save_exception_to_jsonl(config.REPORT_PATH, report_data, str(e))

    log_func(f"报表生成成功: {report_path}", "SUCCESS")


async def report(target_path, log_func, packages=None, is_dir=True):
    """

    :param target_path:
    :param log_func:
    :param packages:
    :param is_dir:  单文件或者批量文件
    :return:
    """

    if is_dir:

        packages = prepare_data(target_path, is_dir)

        if packages:
            for package in packages:
                if not package:
                    continue

                data, group_id = report_data(package)

                if has_error_message(package, data, group_id):
                    # 这里对于数据异常做了处理
                    continue

                generate_docx(data, package, group_id, log_func)

        if target_path.exists() and target_path.is_dir():
            # rmtree 代表 remove tree（删除目录树），它会把文件夹和里面的文件全部删光
            shutil.rmtree(target_path)
            log_func(f"缓存文件被删除: {target_path}", "SUCCESS")
        else:
            log_func("文件夹不存在，无需删除。")

    else:
        if not packages:
            return

        data, group_id = report_data(packages)

        if has_error_message(packages, data, group_id):
            return

        generate_docx(data, packages, group_id, log_func)
