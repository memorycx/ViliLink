"""待维修任务页面。"""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from common.models import RepairTask
from ui.theme import BORDER_COLOR, CARD_BG, SUCCESS_COLOR


class TasksPage(ctk.CTkFrame):
    REFRESH_INTERVAL_MS = 5000

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._timer_id: str | None = None

        ctk.CTkLabel(
            self,
            text="待维修报表列",
            font=ctk.CTkFont(size=30, weight="bold"),
        ).pack(anchor="w", padx=40, pady=(40, 20))

        self.container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=40, pady=10)

        self.refresh()
        self._schedule_refresh()

    def stop_timer(self) -> None:
        if self._timer_id is not None:
            try:
                self.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None

    def refresh(self) -> None:
        for widget in self.container.winfo_children():
            widget.destroy()

        try:
            tasks = self.app.repair_service.list_tasks()
        except Exception as exc:
            self.app.log(f"加载待维修列表失败: {exc}", "ERROR")
            tasks = []

        if not tasks:
            ctk.CTkLabel(
                self.container,
                text="暂无待维修任务",
                text_color="gray60",
                font=ctk.CTkFont(size=15),
            ).pack(pady=40)
            return

        for task in tasks:
            self._render_task(task)

    def _render_task(self, task: RepairTask) -> None:
        card = ctk.CTkFrame(
            self.container,
            height=80,
            corner_radius=15,
            fg_color=CARD_BG,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        card.pack(fill="x", pady=8, padx=5)

        info = ctk.CTkFrame(card, fg_color="transparent")
        info.pack(side="left", padx=20, pady=10)
        ctk.CTkLabel(
            info,
            text=task.filename,
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            info,
            text=f"创建时间: {task.date}",
            text_color="gray",
        ).pack(anchor="w")

        ctk.CTkButton(
            card,
            text="完成",
            width=100,
            fg_color=SUCCESS_COLOR,
            hover_color="#059669",
            command=lambda current=task: self._complete(current),
        ).pack(side="right", padx=20)

    def _complete(self, task: RepairTask) -> None:
        if not messagebox.askyesno("确认操作", f"确定已经完成文件：\n\n{task.filename} ?"):
            return

        try:
            self.app.repair_service.complete(task)
        except Exception as exc:
            self.app.log(f"完成维修任务失败: {exc}", "ERROR")
            messagebox.showerror("操作失败", str(exc))
            return

        self.app.log(f"文件已完成: {task.filename} ({task.date})", "SUCCESS")
        self.refresh()
        messagebox.showinfo("成功", "待维修记录及对应异常报表已删除")

    def _schedule_refresh(self) -> None:
        if not self.winfo_exists():
            return
        self.refresh()
        self._timer_id = self.after(self.REFRESH_INTERVAL_MS, self._schedule_refresh)
