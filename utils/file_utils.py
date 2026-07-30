import json
import os
from pathlib import Path
from datetime import datetime
import random
from dateutil.relativedelta import relativedelta
import re



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
                            print(f"JSON解析失败！文件: {file_path}, 第 {line_num} 行")
                            print(f"错误原因: {e}")
                            print(f"该行内容前600个字符: {line[:600]}")  # 打印到错误位置附近
                            raise e
        return messages

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

    @staticmethod
    def fix_path_ym(path: str) -> str:
        now = datetime.now()
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
