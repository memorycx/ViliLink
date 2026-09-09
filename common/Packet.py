import json
from datetime import datetime


class Packet:
    """
    一个报表中的数据，封装在这里面
    error_code： 0为正常；1为文本有异常；2为图片异常; 3为查找编号异常
    """

    def __init__(self, all_text, image_name, send_time, user_name, message, group_id, town_name, village_name,
                 facility_code, facility_name, process, image_map, error):
        self.all_text = all_text
        self.image_name = image_name or []
        self.user_name = user_name
        self.group_id = group_id
        self.message = message
        self.town_name = town_name
        self.village_name = village_name
        self.facility_code = facility_code
        self.facility_name = facility_name
        self.process = process
        self.image_map = image_map
        self.image_path = []
        self.abnormal_status = "暂无"
        self.error_code = error or []

        self.find_image()

        # 2. 时间戳转换（兼容 string 和 13位毫秒时间戳）
        try:
            ts = float(send_time)
            if ts > 1e11:  # 简单判定：如果是 13 位毫秒时间戳，转为秒
                ts /= 1000
            self.send_time = datetime.fromtimestamp(ts)
        except (ValueError, TypeError):
            self.send_time = None

        self.town = f"{self.town_name} {self.village_name}"

        if not self.facility_name or not self.facility_code or not self.process:
            self.error_code.append("3")

        if message and "异常" in message:
            self.abnormal_status = message.split("异常", 1)[1].strip()

    def find_image(self):
        for name in self.image_name:
            image_path_tem = self.image_map.get(name.lower()) if self.image_map else None
            if image_path_tem is None:
                self.error_code.append("2")
                continue
            self.image_path.append(image_path_tem)

    def to_dict(self):
        """转为字典，格式化 datetime，方便后续 json 化"""
        data = self.__dict__.copy()
        if isinstance(data.get("send_time"), datetime):
            data["send_time"] = data["send_time"].strftime("%Y-%m-%d %H-%M-%S")
        return data

    def to_json(self, ensure_ascii=False, indent=None):
        return json.dumps(self.to_dict(), ensure_ascii=ensure_ascii, indent=indent)

    @classmethod
    def from_dict(cls, json_dict: dict):
        """
        从字典还原 Packet 对象（绕过 __init__ 中的解析逻辑，直接恢复字段值）
        """
        # 创建一个空对象实例
        obj = cls.__new__(cls)

        # 将字典数据更新到对象的 __dict__ 中
        obj.__dict__.update(json_dict)
        return obj

    @classmethod
    def from_json(cls, json_str: str):
        """从 JSON 字符串读取并还原成 Packet 对象"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def __str__(self):
        return self.to_json()
