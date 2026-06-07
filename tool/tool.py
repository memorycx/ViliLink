
import sys
import json
import os
from pathlib import Path

from datetime import datetime
from random import random

import pandas as pd


def find_files_by_partial_name(folder_path, partial_name, recursive=False):
    """
    这个函数返回图片的本地路径
    :param folder_path: 要搜索的文件夹路径
    :param partial_name: 文件名片段
    :param recursive: 是否递归搜索子文件夹
    :return: 匹配到的文件路径列表
    """
    matched_files = []

    partial_name_lower = partial_name.lower()
    folder_path = str(folder_path)

    path_string_list = [p.strip().strip('"\'') for p in folder_path.split(",") if p.strip()]

    # 2. 将它们转换为标准的 Path 对象列表（数组）
    path_list = [Path(p) for p in path_string_list]

    first_path = path_list[0]

    if not first_path.exists():
        return matched_files

    if recursive:
        # 递归遍历所有子文件夹
        # 这里目前没有用到过，先不改
        for root, dirs, files in os.walk(first_path):
            for file in files:
                if partial_name_lower in file.lower():
                    matched_files.append(os.path.join(root, file))
    else:
        # 只搜索当前文件夹

        for file in os.listdir(first_path):
            file_path = os.path.join(first_path, file)

            if os.path.isfile(file_path) and partial_name_lower in file.lower():
                matched_files.append(file_path)

            elif len(path_list) > 1:
                for tem_path in path_list[1:]:
                    if not tem_path.exists():
                        continue
                    # 遍历剩下得路径，寻找相应得文件
                    for file_tem in os.listdir(tem_path):
                        file_path = os.path.join(tem_path, file_tem)
                        if os.path.isfile(file_path) and partial_name_lower in file_tem.lower():
                            matched_files.append(file_path)

    if len(matched_files) > 0:
        return matched_files[0]

    return matched_files


def find_facility_info(town_name, village_name):
    try:

        if getattr(sys, 'frozen', False):
            # 打包后的路径：exe 所在目录
            base_path = os.path.dirname(sys.executable)
        else:
            # 开发时路径：当前脚本所在目录
            base_path = os.path.dirname(os.path.abspath(__file__))

            # 拼接文件路径
        file_path = os.path.join(base_path, "编号集合.xlsx")

        df = pd.read_excel(file_path)
        df.columns = df.columns.str.strip()
        condition = (df['乡镇'] == town_name) & (df['自然村'] == village_name)

        result = df[condition]

        if len(result) == 1:
            if len(result) == 1:
                facility_code = result.iloc[0]['设施编码']
                process = result.iloc[0]['处理工艺']
                return facility_code, process

        else:
            # 走上报流程，人工处理
            return None, None

    except Exception as e:
        print(f"发生错误: {e}")


def load_jsonl_file(file_path):
    """加载jsonl文件，返回消息列表"""
    messages = []
    if os.path.exists(file_path):
        # 推荐使用 utf-8-sig 顺便兼容 BOM 问题
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            for line_num, line in enumerate(f, 1):  # 记录行号
                line = line.strip()
                if line and len(line) > 15:
                    try:
                        messages.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        # 打印出到底是第几行、什么内容导致了报错
                        print(f"❌ JSON解析失败！文件: {file_path}, 第 {line_num} 行")
                        print(f"错误原因: {e}")
                        print(f"该行内容前600个字符: {line[:600]}")  # 打印到错误位置附近
                        raise e  # 抛出异常或选择 continue 跳过
    return messages


def save_exception_to_jsonl(report_path, report_data, error_msg):
    """
    把生成失败的 report_data 完整保存到 jsonl 文件，方便后续重试/排查
    """
    # 异常数据存放目录：报告目录 / unknownError
    base_dir = Path(report_path)
    error_jsonl_dir = base_dir / "unknownError"
    error_jsonl_dir.mkdir(parents=True, exist_ok=True)

    # 每天一个文件
    today = datetime.now().strftime("%Y-%m-%d")
    jsonl_file = error_jsonl_dir / f"{today}_生成失败数据.jsonl"

    exception_data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "error": error_msg,
        "report_path": str(report_path),
        "report_data": report_data
    }

    # 以 JSONL 格式追加写入（每行一个JSON）
    with open(jsonl_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(exception_data, ensure_ascii=False) + "\n")


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

