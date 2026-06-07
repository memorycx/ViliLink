import os
import sys
from pathlib import Path
from dotenv import load_dotenv, set_key


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
    # TOKEN 是机器人主账号的访问令牌，用于连接 WebSocket 服务器
    # TOKEN_SEND 是机器人主账号的访问令牌，用于发送消息
    TOKEN_WEBSOCKET = os.getenv("TOKEN_WEBSOCKET", "")
    TOKEN_SEND = os.getenv("TOKEN_SEND", "")

    # --- 接口地址 ---
    # 动态拼接 WebSocket 路由
    WS_BASE = os.getenv("WS_BASE_URL", "ws://127.0.0.1:3001")
    URL_WEBSOCKET = f"{WS_BASE}?access_token={TOKEN_WEBSOCKET}"

    URL_SEND = os.getenv("URL_SEND", "http://127.0.0.1:6098/send_private_msg")

    HEADERS_SEND = {
        "Authorization": f"Bearer {TOKEN_SEND}"
    }

    # --- 路径管理 ---
    # 使用 Path 对象可以更方便地处理 Windows 路径
    SAVE_ROOT_DIR = Path(os.getenv("SAVE_ROOT_DIR", str(BASE_DIR / "data")))
    LOCAL_IMAGES_DIR = Path(os.getenv("LOCAL_IMAGES_DIR", ""))
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
