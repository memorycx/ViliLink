"""异常数据页面：查看并人工修复异常报表。"""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from common.errors import error_label
from report.regenerate import regenerate_error_report
from ui.theme import DANGER_COLOR, ERROR_CARD_BG
from utils.file_utils import ErrorRecord, load_error_packets


class ErrorsPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        ctk.CTkLabel(
            self,
            text="异常数据列",
            font=ctk.CTkFont(size=30, weight="bold"),
        ).pack(anchor="w", padx=40, pady=(40, 20))

        self.container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=40, pady=10)

        self.refresh()

    def refresh(self) -> None:
        for widget in self.container.winfo_children():
            widget.destroy()

        try:
            records = load_error_packets(self.app.settings.report_path)
        except Exception as exc:
            self.app.log(f"加载异常数据失败: {exc}", "ERROR")
            records = []

        if not records:
            ctk.CTkLabel(
                self.container,
                text="暂无异常数据",
                text_color="gray60",
                font=ctk.CTkFont(size=15),
            ).pack(pady=40)
            return

        for record in records:
            self._render_record(record)

    def _render_record(self, record: ErrorRecord) -> None:
        packet = record.packet

        card = ctk.CTkFrame(
            self.container,
            fg_color=ERROR_CARD_BG,
            corner_radius=10,
        )
        card.pack(fill="x", pady=8, ipady=10, padx=5)
        card.grid_columnconfigure(0, weight=35)
        card.grid_columnconfigure(1, weight=50)
        card.grid_columnconfigure(2, weight=15)

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.grid(row=0, column=0, padx=(20, 10), pady=10, sticky="ew")

        ctk.CTkLabel(
            info,
            text=error_label(packet.error_codes),
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=(DANGER_COLOR, "#F87171"),
            anchor="w",
        ).pack(side="left", padx=(0, 25))

        ctk.CTkLabel(
            info,
            text=f"群: {packet.group_id or '未知群号'}",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w",
        ).pack(side="left", padx=(0, 15))

        send_time = packet.send_time.strftime("%Y-%m-%d %H:%M:%S") if packet.send_time else "未知时间"
        ctk.CTkLabel(
            info,
            text=send_time,
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w",
        ).pack(side="left")

        entry = ctk.CTkEntry(card, font=ctk.CTkFont(size=13))
        entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        entry.insert(0, packet.all_text or "")

        button = ctk.CTkButton(
            card,
            text="确认修改",
            width=100,
            fg_color=("#3B82F6", "#2563EB"),
            hover_color=("#1D4ED8", "#1E40AF"),
        )
        button.configure(
            command=lambda current=record, current_entry=entry, current_button=button: (
                self._regenerate(current, current_entry, current_button)
            )
        )
        button.grid(row=0, column=2, padx=(10, 20), pady=10, sticky="e")

    def _regenerate(self, record: ErrorRecord, entry: ctk.CTkEntry, button: ctk.CTkButton) -> None:
        text = entry.get().strip()
        if not text:
            messagebox.showwarning("提示", "请先填写正确的报表文本。")
            return

        entry.configure(state="disabled")
        button.configure(state="disabled", text="处理中...")
        self.app.log(f"正在重新生成异常数据 {record.file_id}...", "INFO")

        def work() -> bool:
            return regenerate_error_report(
                record=record,
                text=text,
                settings=self.app.settings,
                facility_index=self.app.facility_index,
                image_index=self.app.image_index,
                log_func=self.app.log_threadsafe,
            )

        def done(success: bool) -> None:
            self.refresh()
            if success:
                messagebox.showinfo("成功", "报表已重新生成。")
            else:
                messagebox.showwarning("未完成", "数据仍有异常，已保留在异常列表中，请继续修改。")

        def failed(error: Exception) -> None:
            self.refresh()
            messagebox.showerror("重新生成失败", str(error))

        self.app.run_in_background(work, on_done=done, on_error=failed)
