"""WebSocket 消息监听、批量存档与维修通知入口。"""

from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Mapping

import websockets

from common.config import Settings
from common.models import parse_send_time

if TYPE_CHECKING:
    from repair.service import RepairService

LogFunc = Callable[..., None]


class ChatLogStore:
    """按 群号/日期_用户 分文件追加聊天记录，使用文件级锁避免并发写坏。"""

    def __init__(self, root: str | Path):
        self._root = Path(root)
        self._locks: dict[str, threading.Lock] = {}
        self._guard = threading.Lock()

    def append(self, event: Mapping[str, Any]) -> Path | None:
        group_id = event.get("group_id")
        if group_id is None:
            return None

        sender = event.get("sender") or {}
        user_id = event.get("user_id") or sender.get("user_id") or "unknown"
        send_time = parse_send_time(event.get("time")) or datetime.now()
        day = send_time.strftime("%Y-%m-%d")

        path = self._root / str(group_id) / f"{day}_{user_id}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)

        lock = self._file_lock(str(path.resolve()))
        with lock, path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(dict(event), ensure_ascii=False) + "\n")
        return path

    def _file_lock(self, key: str) -> threading.Lock:
        with self._guard:
            return self._locks.setdefault(key, threading.Lock())


class MessageListener:
    """
    在独立线程中运行 asyncio 事件循环。

    使用 threading.Event 控制生命周期，停止时会主动关闭 WebSocket，
    因此不会像旧实现那样出现“停止后后台仍在监听”的问题。
    """

    def __init__(
        self,
        settings: Settings,
        repair_service: RepairService,
        log_func: LogFunc,
        on_state_change: Callable[[bool], None] | None = None,
        save_threshold: int = 1024,
        save_interval: float = 10.0,
    ):
        self._settings = settings
        self._repair_service = repair_service
        self._log = log_func
        self._on_state_change = on_state_change
        self._store = ChatLogStore(settings.project_root / "chat_logs")
        self._save_threshold = save_threshold
        self._save_interval = save_interval

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._websocket: Any = None
        self._queue: asyncio.Queue[dict[str, Any] | None] | None = None
        self._state_lock = threading.Lock()

    @property
    def is_running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self) -> bool:
        with self._state_lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="villink-listener",
                daemon=True,
            )
            self._thread.start()
            return True

    def stop(self) -> None:
        self._stop_event.set()
        loop = self._loop
        websocket = self._websocket
        if loop is not None and websocket is not None:
            try:
                loop.call_soon_threadsafe(self._close_websocket)
            except RuntimeError:
                pass

    def _close_websocket(self) -> None:
        if self._websocket is not None:
            asyncio.ensure_future(self._websocket.close())

    def _run(self) -> None:
        self._notify_state(True)
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run_forever())
        except Exception as exc:
            self._log(f"监听线程异常退出: {exc}", "ERROR")
        finally:
            try:
                pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            loop.close()

            current = threading.current_thread()
            with self._state_lock:
                is_current = self._thread is current
                if is_current:
                    self._thread = None
                    self._loop = None

            # 避免旧线程退出时覆盖刚启动的新线程状态
            if is_current:
                self._notify_state(False)
                self._log("监听服务已停止", "WARNING")

    async def _run_forever(self) -> None:
        self._queue = asyncio.Queue()
        writer = asyncio.create_task(self._writer_loop(), name="chat-log-writer")
        try:
            await self._listen_loop()
        finally:
            if self._queue is not None:
                self._queue.put_nowait(None)
            try:
                await asyncio.wait_for(writer, timeout=5)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                writer.cancel()

    async def _listen_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                async with websockets.connect(
                    self._settings.websocket_url,
                    open_timeout=5,
                    ping_interval=20,
                    ping_timeout=20,
                ) as websocket:
                    self._websocket = websocket
                    self._log(f"成功连接到消息流: {self._settings.ws_base_url}")

                    while not self._stop_event.is_set():
                        try:
                            raw = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        except asyncio.TimeoutError:
                            continue
                        self._dispatch(raw)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if self._stop_event.is_set():
                    break
                self._log(f"连接异常: {exc}，5 秒后自动重连...", "ERROR")
                await self._sleep(5)
            finally:
                self._websocket = None

    def _dispatch(self, raw: str) -> None:
        try:
            event = json.loads(raw)
        except json.JSONDecodeError as exc:
            self._log(f"收到无法解析的数据: {exc}", "ERROR")
            return

        if not isinstance(event, dict):
            return

        # 心跳包与私聊消息没有 group_id，直接过滤。
        if event.get("group_id") is None or event.get("user_id") is None:
            return

        if self._queue is not None:
            self._queue.put_nowait(event)
        self._log_message(event)

    def _log_message(self, event: Mapping[str, Any]) -> None:
        parts = event.get("message") or []
        first = parts[0] if parts else {}
        kind = first.get("type", "unknown")

        if kind == "text":
            preview = str((first.get("data") or {}).get("text") or "")
        elif kind == "image":
            preview = "[图片]"
        else:
            preview = f"[{kind}]"

        sender = event.get("sender") or {}
        user_name = sender.get("card") or sender.get("nickname") or event.get("user_id")
        self._log(f"群 {event.get('group_id')} | {user_name}: {preview[:100]}")

    async def _writer_loop(self) -> None:
        if self._queue is None:
            return

        batch: list[dict[str, Any]] = []
        while True:
            try:
                item = await asyncio.wait_for(self._queue.get(), timeout=self._save_interval)
            except asyncio.TimeoutError:
                if batch:
                    await self._flush(batch)
                    batch = []
                if self._stop_event.is_set() and self._queue.empty():
                    return
                continue

            if item is None:
                if batch:
                    await self._flush(batch)
                return

            batch.append(item)
            if len(batch) >= self._save_threshold:
                await self._flush(batch)
                batch = []

    async def _flush(self, batch: list[dict[str, Any]]) -> None:
        try:
            await asyncio.to_thread(self._process_batch, list(batch))
        except Exception as exc:
            self._log(f"批量保存失败: {exc}", "ERROR")

    def _process_batch(self, batch: list[dict[str, Any]]) -> None:
        saved = 0
        for event in batch:
            try:
                if self._should_notify(event):
                    self._repair_service.handle(event)
                if self._store.append(event) is not None:
                    saved += 1
            except Exception as exc:
                self._log(f"处理消息失败: {exc}", "ERROR")
        self._log(f"--- 已自动存档 {saved} 条记录 ---")

    @staticmethod
    def _should_notify(event: Mapping[str, Any]) -> bool:
        parts = event.get("message") or []
        first_type = (parts[0] if parts else {}).get("type")
        raw_message = str(event.get("raw_message") or "")
        is_text = first_type == "text"
        is_reply = raw_message.startswith("[CQ:reply")
        return (is_text or is_reply) and "异常" in raw_message

    async def _sleep(self, seconds: float) -> None:
        for _ in range(max(1, int(seconds * 10))):
            if self._stop_event.is_set():
                return
            await asyncio.sleep(0.1)

    def _notify_state(self, running: bool) -> None:
        if self._on_state_change is None:
            return
        try:
            self._on_state_change(running)
        except Exception:
            pass
