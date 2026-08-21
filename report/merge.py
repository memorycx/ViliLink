import os
import traceback
from datetime import date
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from common.Config import config, BASE_DIR
from common.Packet import Packet
from utils.docx_utils import generate_docx_report

from utils.file_utils import FileUtils
from utils.pack_utils import PackUtils


def generate_pool(packets, log_func):
    workers_line = 4
    if len(packets) < 4:
        workers_line = len(packets)
    with ThreadPoolExecutor(
            max_workers=workers_line
    ) as executor:

        futures = []

        for packet in packets:

            if packet.error_code:
                json_str = packet.to_dict()
                file_path = config.REPORT_PATH / 'error_message'
                file_path.mkdir(exist_ok=True)
                FileUtils.save_jsonl_file(file_path, json_str)

                log_func(f"{packet.town} 的 code为 ---> {packet.error_code} ")
                continue

            future = executor.submit(
                generate_docx,
                packet,
                log_func
            )
            log_func(f"{packet.town}合成成功")
            futures.append(future)

        for future in futures:
            try:
                future.result()

            except Exception as e:
                log_func(f"生成失败:{e}")


def generate_docx(packet, log_func):
    # 拿到一组数据，然后遍历

    path_town = packet.town.replace(" ", "_")

    time = packet.send_time
    if isinstance(time, datetime):
        time = packet.send_time.strftime("%Y-%m-%d %H-%M-%S")
    report_path = config.REPORT_PATH / "运维" / f'{path_town}' / (f'{time}'
                                                                  f'_{packet.user_name}.docx')

    report_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        report_path = FileUtils.check_duplicate_file_names(report_path)

        generate_docx_report(report_path, packet)

        if packet.abnormal_status != "暂无":
            report_path = config.REPORT_PATH / "异常" / f'{packet.town}' / f'{packet.user_name}_{packet.send_time.strftime("%Y-%m-%d")}.docx'
            report_path = FileUtils.check_duplicate_file_names(report_path)
            generate_docx_report(
                report_path,
                packet,
                t="农村生活污水设施异常记录表"
            )

        if str(packet.group_id) == config.REPORT_GROUP:
            report_path = config.REPORT_PATH / "维修" / f'{packet.town}' / f'{packet.user_name}_{packet.send_time.strftime("%Y-%m-%d")}.docx'
            report_path = FileUtils.check_duplicate_file_names(report_path)
            generate_docx_report(
                report_path,
                packet,
                t="农村生活污水设施维修记录表"
            )

    except Exception as e:
        log_func(f"报表生成失败，详情请到报告目录下的异常文件中查看")
        log_func(
            traceback.format_exc()
        )
        FileUtils.save_exception_to_jsonl(config.REPORT_PATH, packet, str(e))

    log_func(f"报表生成成功: {report_path}", "SUCCESS")


async def report(log_func, pack_utils, day=None, packages=None, is_dir=True):
    """
    生成报表，界面调用的函数
    两处调用这个函数：批量生成，单文件生成
    :param pack_utils:
    :param day: 选择需要创建的日期，默认为当日
    :param log_func: 日志函数
    :param packages: 是否已经有打包好的数据，默认是 None
    :param is_dir:  单文件或者批量文件，默认是 True; 如果是False,那么packages参数不能是None
    :return:
    """

    chat_log_path = BASE_DIR / "chat_logs"
    file_utils = FileUtils()

    # 需要在上流就控制好图片的日期
    if day is None:
        day = date.today()

    if is_dir:
        pack_utils.get_day_file_map(day)

        day_str = day.strftime("%Y-%m-%d")
        message_list = []
        for item_name in os.listdir(chat_log_path):

            item_full_path = os.path.join(chat_log_path, item_name)

            if os.path.isdir(item_full_path):
                for file in os.listdir(item_full_path):
                    file_full_path = os.path.join(item_full_path, file)
                    if day_str in file:
                        message_list.extend(file_utils.load_jsonl_file(file_full_path))
                        log_func(f"正在处理{file},聊天记录有 ---> {len(message_list)}")

                    packets = []

                    if message_list:
                        image_name_list = []
                        for item in message_list:
                            if item["message"][0]["type"] == "image":
                                image_name = item["message"][0]["data"]["file"]
                                image_name_list.append(image_name)

                            if item["message"][0]["type"] == "text":
                                time = item["time"]
                                user_name = item["sender"]["card"]
                                text = item["message"][0]["data"]["text"]
                                group_id = item["group_id"]
                                error_code = []

                                town_name, village_name, message = PackUtils.parse_message(text, error_code)

                                facility_code, facility_name, process = PackUtils.find_facility_info(
                                    town_name, village_name
                                )

                                if not facility_code or not facility_name or not process:
                                    error_code.append("3")

                                packet = Packet(text, image_name_list, time, user_name, message, group_id, town_name,
                                                village_name,
                                                facility_code, facility_name, process,
                                                pack_utils.image_cache, error_code)

                                image_name_list.clear()
                                packets.append(packet)
                        log_func(f"该群报表有 ------>  {len(packets)}条报表")
                        log_func(f"正在加急生成，请等待!!!")
                        generate_pool(packets, log_func)

                        message_list.clear()
                        packets.clear()
                        log_func("该群报表全部生成完毕~")

        log_func("嘿嘿嘿！全部合成完毕啦~")

        # 这里将今日的文件，全部写入程序内部的哈希表中

        # if target_path.exists() and target_path.is_dir():
        #     # rmtree 代表 remove tree（删除目录树），它会把文件夹和里面的文件全部删光
        #     shutil.rmtree(target_path)
        #     log_func(f"缓存文件被删除: {target_path}", "SUCCESS")
        # else:
        #     log_func("文件夹不存在，无需删除。")

    # else:
    #     if not packages:
    #         return
    #
    #     data, group_id = report_data(packages)
    #
    #     if has_error_message(packages, data, group_id):
    #         log_func(f"有异常")
    #         return
    #
    #     generate_docx(data, packages, group_id, log_func)
