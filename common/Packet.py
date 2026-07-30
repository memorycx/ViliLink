from datetime import datetime

from utils.pack_utils import PackUtils


class Packet:
    """
    一个报表中的数据，封装在这里面
    error_code： 0为正常；1为文本有异常；2为图片异常; 3为查找编号异常
    """
    facility_name = ""
    facility_code = ""
    process = ""
    town = ""
    abnormal_status = ""

    image_name = []
    group_id = ""
    send_time = ""
    user_name = ""
    message = ""

    image_path = []

    error_code = 0

    def __init__(self, image_name, send_time, user_name, message, group_id, image_map):
        self.image_name = image_name
        self.send_time = datetime.fromtimestamp(send_time)
        self.user_name = user_name
        self.group_id = group_id
        self.image_path = []

        message_tem = message.split("，")

        if len(message_tem) < 3:
            self.error_code = 1

        for text in message_tem[2:]:
            self.message = self.message + "," + text

        self.town = message_tem[0] + " " + message_tem[1]
        self.facility_code, self.facility_name, self.process = PackUtils.find_facility_info(message_tem[0],
                                                                                            message_tem[1])
        if not self.facility_name or not self.facility_code or not self.process:
            self.error_code = 3

        for name in image_name:
            image_path_tem = image_map.get(name.lower())
            if image_path_tem is None:
                self.error_code = 2
                continue

            self.image_path.append(image_path_tem)

        if "异常" in message:
            self.abnormal_status = message.split("异常", 1)[1].strip()  # strip() 去掉前后空格
        else:
            self.abnormal_status = "暂无"
