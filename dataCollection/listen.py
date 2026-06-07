import asyncio
import time
import websockets
import json
from datetime import datetime
from config import config, BASE_DIR
from repair.repair_message import repair
import threading
from collections import defaultdict

URL_WEBSOCKET, IS_LISTEN = config.URL_WEBSOCKET, config.IS_LISTEN

# 1. 创建一个全局的字典锁和一个互斥锁，用来保证锁字典本身的线程安全
_file_locks = defaultdict(threading.Lock)
_dict_lock = threading.Lock()

SAVE_THRESHOLD = 30  # 每积攒 30 条存一次
SAVE_INTERVAL = 10  # 或者每 60 秒存一次（防止消息太少一直不存）

buffer = []
last_save_time = time.time()


async def flush_to_disk(log_func):
    """将缓冲区数据写入物理文件"""
    global buffer, last_save_time
    if not buffer:
        return

    try:
        for data in buffer:
            # if data["message"][0]["type"] == "image":
            #     _save_temp(data)

            if data["message"][0]["type"] == "text" or data["raw_message"].startswith("[CQ:reply"):

                if "异常" in data["raw_message"]:
                    repair(data, log_func)

            _save_temp(data)

        log_func(f"--- 已自动存档 {len(buffer)} 条记录 ---", level="SUCCESS")
        buffer.clear()
        last_save_time = time.time()

    except Exception as e:
        log_func(f"保存失败: {e}", level="ERROR")


def get_file_lock(file_path):
    """根据文件路径获取对应的锁（线程安全）"""
    with _dict_lock:
        return _file_locks[file_path]


def _save_temp(data_text):
    """
    关于锁的一些文字说明

    细粒度锁（High Concurrency）：
    我们使用了 defaultdict(threading.Lock)。如果线程 A 在写 群A_张三.jsonl，线程 B 在写 群B_李四.jsonl，它们拿到的不是同一把锁，所以它们会同时并行写入，没有任何性能损失。

    精准排队（Conflict Avoidance）：
    如果线程 A 正在写 群A_张三.jsonl，此时线程 C 也想往 群A_张三.jsonl 写入，线程 C 会在 with current_file_lock: 这一行自动挂起等待，直到 A 写完并关闭文件后，C 才会进去打开并写入，彻底杜绝了多线程同时打开同一个文件导致的冲突或内容错乱。

    安全释放：
    使用 with 语句。即使在写入或者 json.dumps 过程中发生任何意外报错，Python 也会在退出 with 块时百分之百释放锁，不会导致死锁。
    :param data_text:
    :return:
    """

    people = data_text['user_id']
    groups = data_text['group_id']

    json_file_path = BASE_DIR / 'chat_logs' / str(groups)
    json_file_path.mkdir(parents=True, exist_ok=True)

    dt = datetime.fromtimestamp(data_text['time']).strftime('%Y-%m-%d')

    text_file = json_file_path / f"{dt}_{people}.jsonl"

    # 2.获取当前文件专属的锁
    # 转换为绝对路径的字符串作为 key，确保唯一性
    current_file_lock = get_file_lock(str(text_file.resolve()))

    # 3. 加锁写入文件
    # 当 A 任务在写这个文件时，B 任务如果也是写同一个文件，会在 with 这里等待
    with current_file_lock:
        with open(text_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(data_text, ensure_ascii=False) + "\n")


async def listen_messages(log_func):

    try:
        async with websockets.connect(URL_WEBSOCKET) as websocket:

            log_func(f"[{datetime.now().strftime('%H:%M:%S')}] 成功连接到 NapCat 消息流！")
            while IS_LISTEN:



                raw_data = await websocket.recv()
                data = json.loads(raw_data)
                should_write = True

                if time.time() - last_save_time > SAVE_INTERVAL:
                    await flush_to_disk(log_func)

                try:
                    first_key = next(iter(data.keys()), None)
                    if first_key == "time" or "group_id" not in data:
                        should_write = False
                except json.JSONDecodeError:
                    # 如果解析失败，这个消息暂时先丢掉
                    pass

                if should_write:
                    buffer.append(data)
                    log_func(data)

                    if len(buffer) >= SAVE_THRESHOLD:
                        await flush_to_disk(log_func)

    except Exception as e:
        log_func(f"连接异常: {e}，5秒后自动重连...")
        await asyncio.sleep(5)
