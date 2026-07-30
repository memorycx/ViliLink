import os
import sys
from pathlib import Path
from dotenv import load_dotenv, set_key

from utils.file_utils import FileUtils


# 目前还需要对暴露出来的配置项的载入到程序中，测试这一步的功能


def get_base_dir():
    """获取项目根目录，兼容 PyInstaller 打包后的环境"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后的环境
        return Path(sys.executable).parent
    else:
        # 开发环境
        return Path(__file__).parent


BASE_DIR = get_base_dir()

# 加载 .env 文件
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)


class Config:

    # --- 基础认证 ---
    TOKEN_WEBSOCKET = os.getenv("TOKEN_WEBSOCKET", "Wboo6Jl0gyzf8lio")
    TOKEN_SEND = os.getenv("TOKEN_SEND", "ihEyw4Ow7Ip5a58k")

    # --- 接口地址 ---
    WS_BASE = os.getenv("WS_BASE_URL", "ws://127.0.0.1:3001")
    URL_WEBSOCKET = f"{WS_BASE}?access_token={TOKEN_WEBSOCKET}"

    URL_SEND = os.getenv("URL_SEND", "http://127.0.0.1:6098/send_private_msg")

    HEADERS_SEND = {
        "Authorization": f"Bearer {TOKEN_SEND}"
    }

    # --- 路径管理 ---
    # 使用 Path 对象可以更方便地处理 Windows 路径

    DEFAULT_PATHS = (
        r"C:\Users\changxin\Documents\Tencent Files\2823906719\nt_qq\nt_data\Pic\2026-06\Thumb,"
        r"C:\Users\changxin\Documents\Tencent Files\2823906719\nt_qq\nt_data\Pic\2026-06\ThumbTemp,"
        r"C:\Users\changxin\Documents\Tencent Files\2823906719\nt_qq\nt_data\Pic\2026-06\Ori,"
        r"C:\Users\changxin\Documents\Tencent Files\2823906719\nt_qq\nt_data\Pic\2026-06\OriTemp"
    )

    SAVE_ROOT_DIR = Path(os.getenv("SAVE_ROOT_DIR", str(BASE_DIR / "data")))
    raw_paths = os.getenv("LOCAL_IMAGES_DIR", DEFAULT_PATHS)

    # 3. 解析为 Path 对象列表
    LOCAL_IMAGES_DIR = [
        Path(FileUtils.fix_path_ym(p.strip()))
        for p in raw_paths.split(",")
        if p.strip()
    ]

    LOCAL_IMAGES_DIR_LAST_MONTH = [
        Path(FileUtils.fix_path_last_ym(p.strip()))
        for p in raw_paths.split(",")
        if p.strip()
    ]


    TESSERACTS_CMD = Path(os.getenv("TESSERACTS_CMD", ""))
    REPORT_PATH = Path(os.getenv("REPORT_PATH", ""))
    FIX_PATH = Path(os.getenv("FIX_PATH", ""))

    # --- 运行状态 ---
    # 环境取出的值是字符串，需要转为布尔值
    IS_LISTEN = os.getenv("IS_LISTEN", "True").lower() == "true"

    # -----维修人员的qq ---

    REPORT_PEOPLE_QQ = os.getenv("REPORT_PEOPLE_QQ", "")
    REPORT_GROUP = os.getenv("REPORT_GROUP", "")


# 实例化，方便直接导入使用
config = Config()


def set_config(key: str, value: str | Path | bool, log):
    """
    修改配置并自动保存到 .env 文件
    使用示例：
    set_config("TOKEN", "新的TOKEN")
    """

    if isinstance(value, bool):
        value_str = "True" if value else "False"
    elif isinstance(value, Path):
        value_str = str(value)
    else:
        value_str = str(value)

    if hasattr(Config, key):
        setattr(Config, key, value)

    if not env_path.exists():
        env_path.touch()  # 不存在就创建

    set_key(str(env_path), key, value_str)
    log(f"✅ 已保存配置：{key} = {value_str}")
