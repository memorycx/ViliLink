"""主页：监听、报表生成、合并与日志输出。"""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from ui.theme import (
    ACCENT_COLOR,
    BORDER_COLOR,
    CARD_BG,
    DANGER_COLOR,
    LOG_COLORS,
    SUCCESS_COLOR,
)


class HomePage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._busy = False
        self._stopping = False

        self._build_header()
        self._build_cards()
        self._build_log()

        self.log_text.configure(state="disabled")
        self.app.set_log_widget(self.log_text)
        self._update_controls()

    # ---------------- 布局 ----------------
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=40, pady=(50, 30))

        ctk.CTkLabel(
            header,
            text="主页控制台",
            font=ctk.CTkFont(size=32, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            header,
            text="实时数据流监控与自动化报表中心",
            text_color="gray60",
            font=ctk.CTkFont(size=15),
        ).pack(anchor="w", pady=5)

    def _build_cards(self) -> None:
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="x", padx=30)
        for column in range(3):
            container.grid_columnconfigure(column, weight=1)

        listen_card, self.listen_btn = self._task_card(
            container,
            "数据监听",
            "📡",
            "实时采集 WebSocket 与 API 数据流",
            "启动服务",
            self.toggle_listening,
            ACCENT_COLOR,
        )
        listen_card.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        report_card, self.report_btn = self._task_card(
            container,
            "自动化报表",
            "📊",
            "将监听历史转化为可视化 Word 报表",
            "生成报告",
            self.generate_reports,
            SUCCESS_COLOR,
        )
        report_card.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        merge_card, self.merge_btn = self._task_card(
            container,
            "合并数据",
            "📌",
            "合并多人当日同地点的报表",
            "合并",
            self.merge_reports,
            ACCENT_COLOR,
        )
        merge_card.grid(row=0, column=2, padx=10, pady=10, sticky="ew")

    def _task_card(self, master, title, icon, description, button_text, command, color):
        card = ctk.CTkFrame(
            master,
            fg_color=CARD_BG,
            corner_radius=20,
            width=380,
            height=220,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        card.pack_propagate(False)

        ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=40)).pack(pady=(25, 5))
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=20, weight="bold")).pack()
        ctk.CTkLabel(
            card,
            text=description,
            text_color="gray",
            font=ctk.CTkFont(size=13),
        ).pack(pady=5)

        button = ctk.CTkButton(
            card,
            text=button_text,
            fg_color=color,
            hover_color=color,
            width=160,
            height=40,
            corner_radius=10,
            font=ctk.CTkFont(weight="bold"),
            command=command,
        )
        button.pack(pady=(15, 0))
        return card, button

    def _build_log(self) -> None:
        container = ctk.CTkFrame(
            self,
            fg_color=CARD_BG,
            corner_radius=15,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        container.pack(fill="both", expand=True, padx=40, pady=30)

        header = ctk.CTkFrame(container, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(header, text="系统日志输出", font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkButton(
            header,
            text="清除日志",
            width=80,
            height=25,
            fg_color="transparent",
            border_width=1,
            command=self.clear_log,
        ).pack(side="right")

        self.log_text = ctk.CTkTextbox(
            container,
            fg_color=("#F8FAFC", "#0F172A"),
            text_color="#94A3B8",
            font=("Consolas", 13),
            corner_radius=10,
            border_spacing=10,
        )
        self.log_text.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        for level, color in LOG_COLORS.items():
            self.log_text.tag_config(level, foreground=color)
        self.log_text.tag_config("time", foreground="#64748B")

    def clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    # ---------------- 监听 ----------------
    def toggle_listening(self) -> None:
        if self._busy:
            return

        if self._stopping:
            self.app.log("监听服务正在停止，请稍候", "WARNING")
            return

        if self.app.listener.is_running:
            self._stopping = True
            self.app.listener.stop()
            self.app.log("正在停止监听服务...", "WARNING")
            self._update_controls()
        elif self.app.listener.start():
            self.app.log("数据监听服务已启动", "SUCCESS")
        else:
            self.app.log("监听线程尚未完全退出，请稍后再试", "WARNING")

    def on_listener_state(self, running: bool) -> None:
        self._stopping = False
        self.app.set_status(
            "监听中" if running else "待命",
            SUCCESS_COLOR if running else DANGER_COLOR,
        )
        self._update_controls()

    # ---------------- 报表 / 合并 ----------------
    def generate_reports(self) -> None:
        if self._busy:
            return
        if self.app.listener.is_running or self._stopping:
            self.app.log("请先停止监听服务，再生成报表", "WARNING")
            return
        self._set_busy(True)
        self.app.log("报表引擎启动，正在分析历史缓存数据...", "INFO")
        self.app.run_in_background(
            self.app.report_generator.generate_for_day,
            on_done=self._report_done,
            on_error=self._task_failed,
        )

    def _report_done(self, count: int) -> None:
        self._set_busy(False)
        self.app.errors_page.refresh()
        messagebox.showinfo("报表生成", f"本次共生成 {count} 份报表。")

    def merge_reports(self) -> None:
        if self._busy:
            return
        self._set_busy(True)
        self.app.log("正在合并当日同地点报表...", "INFO")
        self.app.run_in_background(
            self.app.merger.merge_today,
            on_done=self._merge_done,
            on_error=self._task_failed,
        )

    def _merge_done(self, count: int) -> None:
        self._set_busy(False)
        messagebox.showinfo("合并完成", f"本次共生成 {count} 份合并报表。")

    def _task_failed(self, error: Exception) -> None:
        self._set_busy(False)
        messagebox.showerror("任务失败", str(error))

    # ---------------- 状态 ----------------
    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_controls()

    def _update_controls(self) -> None:
        listening = self.app.listener.is_running

        if self._stopping:
            self.listen_btn.configure(state="disabled", text="停止中...")
        elif self._busy:
            self.listen_btn.configure(state="disabled", text="停止服务" if listening else "启动服务")
        else:
            self.listen_btn.configure(
                state="normal",
                text="停止服务" if listening else "启动服务",
                fg_color=DANGER_COLOR if listening else ACCENT_COLOR,
                hover_color="#DC2626" if listening else ACCENT_COLOR,
            )

        report_state = "disabled" if self._busy or listening else "normal"
        self.report_btn.configure(state=report_state)
        self.merge_btn.configure(state="disabled" if self._busy else "normal")
