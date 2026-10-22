"""应用主窗口与页面导航。"""

from __future__ import annotations

import queue
import threading
import traceback
from datetime import datetime
from typing import Any, Callable

import customtkinter as ctk

from common.config import load_settings
from dataCollection.listener import MessageListener
from repair.notifier import QQNotifier
from repair.service import RepairService
from report.generator import ReportGenerator
from report.merger import ReportMerger
from ui.pages.errors import ErrorsPage
from ui.pages.home import HomePage
from ui.pages.settings import SettingsPage
from ui.pages.tasks import TasksPage
from ui.theme import (
    ACCENT_COLOR,
    BG_CONTENT,
    BG_SIDEBAR,
    DANGER_COLOR,
    LOG_COLORS,
    NAV_HOVER,
    NAV_TEXT,
    configure_theme,
)
from utils.facility_index import FacilityIndex
from utils.image_index import ImageIndex
from utils.resources import ICON_PATH

BACKGROUND_WORKER = Callable[[], Any]
UI_CALLBACK = Callable[[Any], None]


class App(ctk.CTk):
    def __init__(self):
        configure_theme()
        super().__init__()

        self.settings = load_settings()
        self._closing = False
        self._events: queue.Queue[tuple[Any, ...]] = queue.Queue()
        self._log_textbox: ctk.CTkTextbox | None = None
        self._drain_after_id: str | None = None

        # 服务层
        self.facility_index = FacilityIndex(
            self.settings.facility_file,
            log_func=self.log_threadsafe,
        )
        self.image_index = ImageIndex(
            self.settings.resolved_image_dirs,
            log_func=self.log_threadsafe,
        )
        self.notifier = QQNotifier(self.settings)
        self.repair_service = RepairService(
            self.settings,
            self.notifier,
            self.log_threadsafe,
        )
        self.report_generator = ReportGenerator(
            self.settings,
            self.facility_index,
            self.image_index,
            self.log_threadsafe,
        )
        self.merger = ReportMerger(self.settings, self.log_threadsafe)
        self.listener = MessageListener(
            self.settings,
            self.repair_service,
            self.log_threadsafe,
            on_state_change=self._on_listener_state,
        )

        self._configure_window()
        self._build_sidebar()
        self._build_content()

        self.theme_mode = "dark"
        self._show_page("home")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._drain_after_id = self.after(100, self._drain_events)

    # ---------------- 窗口 ----------------
    def _configure_window(self) -> None:
        self.title("SmartStream | 数据监听管理系统")
        self.geometry("1280x850")
        self.minsize(1100, 750)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        if ICON_PATH.is_file():
            try:
                self.iconbitmap(str(ICON_PATH))
            except Exception:
                # 某些 Linux 桌面环境不支持 .ico，忽略即可。
                pass

    def _build_sidebar(self) -> None:
        self.sidebar = ctk.CTkFrame(
            self,
            width=260,
            corner_radius=0,
            fg_color=BG_SIDEBAR,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        logo_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_container.pack(pady=(40, 40), padx=20, fill="x")
        ctk.CTkLabel(
            logo_container,
            text="SmartStream",
            font=ctk.CTkFont(size=26, weight="bold", family="Inter"),
        ).pack(side="left", padx=10)

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        self._add_nav_button("home", "🏠  主页控制台")
        self._add_nav_button("tasks", "📂  待维修")
        self._add_nav_button("error", "⚠  异常数据列")
        self._add_nav_button("config", "⚙️  系统配置")

        divider = ctk.CTkFrame(
            self.sidebar,
            height=2,
            fg_color=("#CBD5E1", "#374151"),
        )
        divider.pack(fill="x", padx=20, pady=20)

        self.theme_btn = ctk.CTkButton(
            self.sidebar,
            text="🌙 深色模式",
            height=45,
            corner_radius=10,
            fg_color="transparent",
            border_width=1,
            text_color=NAV_TEXT,
            command=self.toggle_theme,
        )
        self.theme_btn.pack(fill="x", padx=20, pady=10)

        status_box = ctk.CTkFrame(
            self.sidebar,
            fg_color=("#F1F5F9", "#1F2937"),
            corner_radius=12,
        )
        status_box.pack(side="bottom", fill="x", padx=20, pady=30)

        self.status_dot = ctk.CTkLabel(
            status_box,
            text="●",
            text_color=DANGER_COLOR,
            font=("Arial", 18),
        )
        self.status_dot.pack(side="left", padx=(15, 5), pady=10)

        self.status_label = ctk.CTkLabel(
            status_box,
            text="系统状态: 待命",
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.status_label.pack(side="left", pady=10)

    def _add_nav_button(self, page_id: str, text: str) -> None:
        button = ctk.CTkButton(
            self.sidebar,
            text=text,
            height=50,
            corner_radius=10,
            anchor="w",
            font=ctk.CTkFont(size=15),
            fg_color="transparent",
            text_color=NAV_TEXT,
            hover_color=NAV_HOVER,
            command=lambda target=page_id: self._show_page(target),
        )
        button.pack(fill="x", padx=20, pady=5)
        self.nav_buttons[page_id] = button

    def _build_content(self) -> None:
        self.content = ctk.CTkFrame(self, fg_color=BG_CONTENT, corner_radius=0)
        self.content.grid(row=0, column=1, sticky="nsew")

        self.home_page = HomePage(self.content, self)
        self.tasks_page = TasksPage(self.content, self)
        self.errors_page = ErrorsPage(self.content, self)
        self.settings_page = SettingsPage(self.content, self)

        self.pages = {
            "home": self.home_page,
            "tasks": self.tasks_page,
            "error": self.errors_page,
            "config": self.settings_page,
        }

    def _show_page(self, page_id: str) -> None:
        for page in self.pages.values():
            page.pack_forget()
        self.pages[page_id].pack(fill="both", expand=True)

        for button_id, button in self.nav_buttons.items():
            if button_id == page_id:
                button.configure(fg_color=ACCENT_COLOR, text_color="white")
            else:
                button.configure(fg_color="transparent", text_color=NAV_TEXT)

        if page_id == "error":
            self.errors_page.refresh()
        elif page_id == "tasks":
            self.tasks_page.refresh()

    # ---------------- 日志与状态 ----------------
    def set_log_widget(self, widget: ctk.CTkTextbox) -> None:
        self._log_textbox = widget
        for level, color in LOG_COLORS.items():
            widget.tag_config(level, foreground=color)
        widget.tag_config("time", foreground="#64748B")

    def log(self, message: Any, level: str = "INFO") -> None:
        textbox = self._log_textbox
        if textbox is None:
            return
        try:
            if not textbox.winfo_exists():
                return
            textbox.configure(state="normal")
            textbox.insert("end", f"[{datetime.now():%H:%M:%S}] ", "time")
            textbox.insert("end", f"[{level}] ", level)
            textbox.insert("end", f"{message}\n")

            line_count = int(textbox.index("end-1c").split(".")[0])
            if line_count > 3000:
                textbox.delete("1.0", "501.0")

            textbox.see("end")
            textbox.configure(state="disabled")
        except Exception:
            pass

    def log_threadsafe(self, message: Any, level: str = "INFO") -> None:
        if self._closing:
            return
        self._events.put(("log", str(message), level))

    def set_status(self, text: str, color: str) -> None:
        self.status_dot.configure(text_color=color)
        self.status_label.configure(text=f"系统状态: {text}")

    # ---------------- 后台任务 ----------------
    def run_in_background(
        self,
        work: BACKGROUND_WORKER,
        on_done: UI_CALLBACK | None = None,
        on_error: UI_CALLBACK | None = None,
        name: str = "villink-task",
    ) -> None:
        def runner() -> None:
            try:
                result = work()
            except Exception as exc:
                self.log_threadsafe(traceback.format_exc(), "ERROR")
                if on_error is not None:
                    self._events.put(("callback", on_error, exc))
            else:
                if on_done is not None:
                    self._events.put(("callback", on_done, result))

        threading.Thread(target=runner, name=name, daemon=True).start()

    def _drain_events(self) -> None:
        try:
            while True:
                event = self._events.get_nowait()
                kind = event[0]
                if kind == "log":
                    self.log(event[1], event[2])
                elif kind == "callback":
                    callback, argument = event[1], event[2]
                    try:
                        callback(argument)
                    except Exception:
                        self.log(traceback.format_exc(), "ERROR")
                elif kind == "listener_state":
                    self.home_page.on_listener_state(bool(event[1]))
        except queue.Empty:
            pass

        if not self._closing:
            self._drain_after_id = self.after(100, self._drain_events)

    def _on_listener_state(self, running: bool) -> None:
        if not self._closing:
            self._events.put(("listener_state", running))

    # ---------------- 主题 ----------------
    def toggle_theme(self) -> None:
        if self.theme_mode == "dark":
            ctk.set_appearance_mode("light")
            self.theme_mode = "light"
            self.theme_btn.configure(text="☀️ 白天模式")
            self.content.configure(fg_color=BG_CONTENT[0])
        else:
            ctk.set_appearance_mode("dark")
            self.theme_mode = "dark"
            self.theme_btn.configure(text="🌙 深色模式")
            self.content.configure(fg_color=BG_CONTENT[1])

    # ---------------- 退出 ----------------
    def _on_close(self) -> None:
        self._closing = True
        try:
            self.listener.stop()
        except Exception:
            pass
        self.tasks_page.stop_timer()
        if self._drain_after_id is not None:
            try:
                self.after_cancel(self._drain_after_id)
            except Exception:
                pass
        self.destroy()
