import json
import os
from pathlib import Path
from datetime import datetime
import random
from uuid import uuid4

from dateutil.relativedelta import relativedelta
import re

from common.Packet import Packet


class FileUtils:
    @staticmethod
    def load_jsonl_file(file_path):
        messages = []
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                for line_num, line in enumerate(f, 1):  # 记录行号
                    line = line.strip()
                    if line and len(line) > 15:
                        try:
                            messages.append(json.loads(line))
                        except json.JSONDecodeError as e:
                            # 打印出到底是第几行、什么内容导致了报错
                            print(f"该行内容前600个字符: {line[:600]}")  # 打印到错误位置附近
                            print(f"json解析失败文件: {file_path}, 第 {line_num} 行")
                            print(f"错误原因: {e}")
                            raise e
        return messages

    @staticmethod
    def load_error_data(dir_path):
        """
        加载 error_message 目录下的异常数据文件（每个文件是一份 Packet 的 JSON）
        返回 Packet 对象列表，并为每个对象附加 file_id（来自文件名），便于重新生成时定位文件
        """
        error_list = []
        if not os.path.isdir(dir_path):
            return error_list

        for file_name in os.listdir(dir_path):
            file_path = os.path.join(dir_path, file_name)
            if not os.path.isfile(file_path):
                continue

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    json_str = f.read()
                packet = Packet.from_json(json_str)
                packet.error_code = list(set(packet.error_code))
            except (json.JSONDecodeError, OSError):
                # 单个坏文件不影响整体加载
                continue

            # 从文件名提取唯一标识：error_message_{id}.jsonl -> {id}
            stem = os.path.splitext(file_name)[0]
            prefix = "error_message_"
            packet.file_id = stem[len(prefix):] if stem.startswith(prefix) else stem
            error_list.append(packet)

        return error_list

    @staticmethod
    def save_exception_to_jsonl(report_path, data, error_msg):
        """
        把生成失败的 report_data 完整保存到 jsonl 文件，方便后续重试/排查
        """
        base_dir = Path(report_path)
        error_jsonl_dir = base_dir / "unknownError"
        error_jsonl_dir.mkdir(parents=True, exist_ok=True)

        jsonl_file = error_jsonl_dir / f"{data.send_time}_生成失败数据.jsonl"

        # exception_data = {
        #     "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        #     "error": error_msg,
        #     "report_path": str(report_path),
        #     "report_data": report_data
        # }
        #
        # with open(jsonl_file, "a", encoding="utf-8") as f:
        #     f.write(json.dumps(exception_data, ensure_ascii=False) + "\n")

    @staticmethod
    def check_duplicate_file_names(report_path):
        """
        检查报告目录下是否有重复的文件名
        """

        # 2. 检查文件是否存在，如果存在则添加6位随机数
        if report_path.exists():
            # 分离出父目录（parent）和原始文件名（stem 是文件名，suffix 是扩展名）
            parent_dir = report_path.parent
            base_name = report_path.stem  # 比如 "2026-05-26_admin"
            suffix = report_path.suffix  # 比如 ".docx"

            while True:
                # 生成 6 位随机数，使用 zfill(6) 确保如果是 001234 也能保持 6 位
                random_num = str(random.randint(0, 999999)).zfill(6)

                new_path = parent_dir / f"{base_name}_{random_num}{suffix}"
                if not new_path.exists():
                    report_path = new_path
                    break

        return report_path

    # @staticmethod
    # def fix_path_ym(path: str) -> str:
    #     now = datetime.now()
    #     target_ym = now.strftime("%Y-%m")
    #     # 正则匹配 2000~2099-01~12 格式：20xx-xx
    #     pattern = re.compile(r"20\d{2}-(0[1-9]|1[0-2])")
    #     return pattern.sub(target_ym, path)
    @staticmethod
    def fix_path_ym(path: str) -> str:
        now = datetime.now()

        # 如果今天是1号，则使用上个月
        if now.day == 1:
            if now.month == 1:
                target_ym = f"{now.year - 1}-12"
            else:
                target_ym = f"{now.year}-{now.month - 1:02d}"
        else:
            target_ym = now.strftime("%Y-%m")

        # 正则匹配 2000~2099-01~12 格式：20xx-xx
        pattern = re.compile(r"20\d{2}-(0[1-9]|1[0-2])")

        return pattern.sub(target_ym, path)

    @staticmethod
    def fix_path_last_ym(path: str) -> str:
        now = datetime.now()
        # 减去1个月，获取上月年月
        last_month = now - relativedelta(months=1)
        target_ym = last_month.strftime("%Y-%m")
        # 匹配 YYYY-MM 格式年月
        pattern = re.compile(r"20\d{2}-(0[1-9]|1[0-2])")
        return pattern.sub(target_ym, path)

    @staticmethod
    def save_jsonl_file(file_path, packet_str):

        path = os.path.join(
            file_path,
            f"error_message_{uuid4().hex}.jsonl"
        )
        print(f"{path}")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(packet_str, f, ensure_ascii=False)
