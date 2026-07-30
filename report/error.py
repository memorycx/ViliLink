import json
import os
from uuid import uuid4

from common.Config import config


def save_json_arrays(data_groups, save_path):
    """
    将错误的数据，保存起来，方便人工改，
    每组异常文件生成一个的jsonl文件，
    文件名，使用随机算法生成。
    :param data_groups: 列表套列表套字典，例如  [{},{}]
    :param save_path: 保存路径
    """
    with open(save_path, "w", encoding="utf-8") as f:
        json.dump(data_groups, f, ensure_ascii=False, indent=2)


def load_json_error(load_path):
    """
    从文件读取多个 JSON 数组，恢复成原来的分组结构
    :return: 原始分组数据  [{},{}]
    """
    if not os.path.exists(load_path):
        return []

    error_message = []

    for file in os.listdir(load_path):
        message = {"file": file}
        message_temp = []
        with open(os.path.join(load_path, file), "r", encoding="utf-8") as f:
            message_temp.extend(json.load(f))

        name_part = file.split(".json")[0]
        random_num = name_part.split("_")[-1]

        message["id"] = random_num
        message["reason"] = message_temp[0]["error_message"]

        if message_temp and message_temp[0] == "图片异常":
            message["group_id"] = message_temp[-1]["group_id"]
            message["time"] = message_temp[-1]["time"]
            message["content"] = ""
            error_message.append(message.copy())

        else:
            message["error"] = message_temp[0]
            message["group_id"] = message_temp[-1]["group_id"]
            message["time"] = message_temp[-1]["time"]
            text = ""
            for i in range(len(message_temp) - 1, 0, -1):
                if message_temp[i]["is_text"]:
                    text += message_temp[i]["raw_message"] + " ||  "
            message["content"] = text
            error_message.append(message.copy())

    return error_message


def error_report_save(package, error_message):
    """
    唯一向外暴露，处理异常数据包
    """

    file_path = config.REPORT_PATH / 'error_message'
    file_path.mkdir(exist_ok=True)

    end_data = package.copy()
    end_data.insert(0, {"error_message": error_message})

    path = os.path.join(
        file_path,
        f"error_message_{uuid4().hex}.jsonl"
    )

    # path = check_duplicate_file_names(path)

    save_json_arrays(end_data, path)






