# 备份维修消息 --> repair_message.jsonl
# 按照日期建立文件
# 通知维修师傅 --> 上报人，上报人的qq账号，上报的消息发给维修师傅
import json
from datetime import datetime

from common.Config import config

from repair.send_message import send_message

from utils.file_utils import FileUtils



def _save_repair_message(data):
    file_path = config.REPORT_PATH / 'repair_message.jsonl'

    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False) + '\n')


def _parse_repair_message(data):
    user_id = data['user_id']
    user_name = data["sender"].get("card")
    if not user_name:
        user_name = data["sender"]["nickname"]
    message = data['raw_message']

    text = (f"姓名：{user_name} \n"
            f"qq账号：{user_id} \n"
            f"上报消息： {message}")
    return text


def parse_repair_message():
    """
    将异常数据清洗出来，返回规格化的数据展示在UI界面中
    :return:
    """
    file_path = config.REPORT_PATH / 'repair_message.jsonl'
    message = FileUtils.load_jsonl_file(file_path)

    message_list = []

    for data in message:
        if data["message"][0]["type"] == "text":
            tem = data["raw_message"].split("，")

            if len(tem) < 2:
                continue

            dt_object = datetime.fromtimestamp(data["time"])
            dt = dt_object.strftime("%Y-%m-%d")
            town, village = tem[0], tem[1]
            message_list.append({
                'filename': f'{town}_{village}',
                "create_time": f"{dt}"
            })

    return message_list


def delete_repair_message(target_task):
    """
    根据传入的规格化数据，删除 jsonl 文件中对应的原始行
    :param target_task: 例如 {'filename': '芝英镇_黄店村', 'create_time': '2026-05-26'}
    """
    file_path = config.REPORT_PATH / 'repair_message.jsonl'

    # 1. 拆解出你要删除的目标特征
    target_town, target_village = target_task['filename'].split('_')
    target_date = target_task['create_time']

    remaining_messages = []

    # 2. 逐行读取文件，过滤掉目标数据
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            data = json.loads(line)

            # 复现你的清洗逻辑，提取当前行的特征进行比对
            if data.get("message") and data["message"][0]["type"] == "text":
                tem = data["raw_message"].split("，")
                dt_object = datetime.fromtimestamp(data["time"])
                dt = dt_object.strftime("%Y-%m-%d")
                town, village = tem[0], tem[1]

                if town == target_town and village == target_village and dt == target_date:
                    print(f"🔥 成功匹配并准备删除：{town}_{village} ({dt})")
                    continue

            remaining_messages.append(data)

    # 3. 将剩下（未被删除）的数据重新写回 jsonl 文件
    with open(file_path, 'w', encoding='utf-8') as f:
        for data in remaining_messages:
            if hasattr(data.get("time"), 'strftime'):
                data["time"] = data["time"].strftime("%Y-%m-%d %H:%M:%S")

            f.write(json.dumps(data, ensure_ascii=False) + '\n')


def delete_repair_report(target):
    target_town, target_village = target['filename'].split('_')
    target_date = target['create_time']

    report_path = config.REPORT_PATH / "异常" / f"{target_town}_{target_village}"

    if report_path.exists() and report_path.is_dir():
        for file in report_path.iterdir():
            if file.is_file():
                if target_date in file.name:
                    file.unlink()
    else:
        print(f"路径不存在或不是文件夹: {report_path}")


def _send_repair_message(text):
    return send_message(text)


def repair(data, log_func):
    _save_repair_message(data)
    text = _parse_repair_message(data)
    if _send_repair_message(text) == 200:
        log_func(f"通知成功")
    else:
        log_func(f"通知失败，请手动联系")
