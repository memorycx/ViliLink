import sys
import os
from datetime import date
import pandas as pd

from common.Config import config


class PackUtils:
    image_cache = {}

    @staticmethod
    def parse_message(message, error):

        message_tem = message.split("，") if message else []
        if len(message_tem) < 3:
            error.append("1")
            return None, None, None

        message = ",".join(message_tem[2:])

        return message_tem[0], message_tem[1], message

    @staticmethod
    def find_facility_info(town_name, village_name):
        """
        查找设备编号，和处理工艺,设备名称
        :param town_name:
        :param village_name:
        :return:
        """
        if town_name and village_name:

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
                        facility_name = result.iloc[0]["设施名称"]
                        return facility_code, facility_name, process

                else:
                    # 走上报流程，人工处理
                    return None, None, None

            except Exception as e:
                print(f"查找编号的时候发生错误: {e}")
                return None, None, None

        else:
            return None, None, None

    def get_day_file_map(self, file_day):
        """
        得到具体日期中修改的所有文件
        :return: dict[文件名: 文件完整路径]
        """

        all_list = config.ALL_IMAGES_DIR

        print("查找的照片的所有目录如下：")
        for list_a in all_list:
            print(list_a)

        for abs_path in all_list:
            # 判断目录是否存在，不存在直接返回空字典（不抛异常）
            if not abs_path:
                continue
            if not os.path.isdir(abs_path):
                return

            with os.scandir(abs_path) as entries:
                for entry in entries:
                    if entry.is_file(follow_symlinks=False):
                        stat_info = entry.stat()
                        create_ts = stat_info.st_ctime
                        file_date = date.fromtimestamp(create_ts)
                        if file_date == file_day:

                            name, ext = os.path.splitext(entry.name)
                            name = name.lower()

                            # 去除末尾 _数字
                            if "_" in name:
                                parts = name.rsplit("_", 1)
                                if parts[1].isdigit():
                                    name = parts[0]

                            self.image_cache[name + ext.lower()] = entry.path

        return


if __name__ == '__main__':
    pack_utils = PackUtils()
    d = date(2026, 7, 27)
    pack_utils.get_day_file_map(d)
    print(pack_utils.image_cache)
