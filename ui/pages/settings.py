"""系统配置页面。"""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from ui.theme import BORDER_COLOR, CARD_BG

FIELDS = (
    ("TOKEN_WEBSOCKET", "访问令牌"),
    ("WS_BASE_URL", "WebSocket 基础地址"),
    ("TOKEN_SEND", "发送令牌"),
    ("URL_SEND", "发送地址"),
    ("REPORT_PATH", "报表保存根目录"),
    ("LOCAL_IMAGES_DIR", "本地QQ图片目录（逗号分隔）"),
    ("REPORT_PEOPLE_QQ", "维修人员 QQ"),
    ("REPORT_GROUP", "维修群号"),
)


class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.entries: dict[str, ctk.CTkEntry] = {}

        ctk.CTkLabel(
            self,
            text="配置中心",
            font=ctk.CTkFont(size=32, weight="bold"),
        ).pack(anchor="w", padx=40, pady=(50, 30))

        form = ctk.CTkScrollableFrame(self, fg_color="transparent")
        form.pack(fill="both", expand=True, padx=40, pady=0)

        card = ctk.CTkFrame(
            form,
            fg_color=CARD_BG,
            corner_radius=20,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        card.pack(fill="x", pady=10)

        for key, label in FIELDS:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=30, pady=12)

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(
                info,
                text=key,
                font=ctk.CTkFont(size=15, weight="bold"),
            ).pack(anchor="w")
            ctk.CTkLabel(
                info,
                text=label,
                font=ctk.CTkFont(size=12),
                text_color="gray",
            ).pack(anchor="w")

            entry = ctk.CTkEntry(row, width=430, height=40, corner_radius=8)
            entry.pack(side="right", padx=10)
            entry.insert(0, self._current_value(key))
            self.entries[key] = entry

        ctk.CTkButton(
            form,
            text="确认并保存更改",
            height=50,
            width=250,
            corner_radius=12,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self.save,
        ).pack(pady=30)

    def _current_value(self, key: str) -> str:
        settings = self.app.settings
        if key == "TOKEN_WEBSOCKET":
            return settings.token_websocket
        if key == "WS_BASE_URL":
            return settings.ws_base_url
        if key == "TOKEN_SEND":
            return settings.token_send
        if key == "URL_SEND":
            return settings.url_send
        if key == "REPORT_PATH":
            return str(settings.report_path)
        if key == "LOCAL_IMAGES_DIR":
            return ",".join(str(path) for path in settings.image_dirs)
        if key == "REPORT_PEOPLE_QQ":
            return settings.report_people_qq
        if key == "REPORT_GROUP":
            return settings.report_group
        return ""

    def save(self) -> None:
        changed = 0
        errors = 0
        for key, entry in self.entries.items():
            value = entry.get().strip()
            if not value:
                self.app.log(f"配置 {key} 为空，已跳过", "WARNING")
                continue
            try:
                self.app.settings.update(key, value)
            except Exception as exc:
                errors += 1
                self.app.log(f"保存配置 {key} 失败: {exc}", "ERROR")
                continue
            changed += 1

        self.app.image_index.set_directories(self.app.settings.resolved_image_dirs)
        self.app.log(
            f"系统配置已更新（{changed} 项）；监听地址相关修改会在下次连接时生效",
            "WARNING",
        )
        if errors:
            messagebox.showwarning(
                "配置",
                f"已保存 {changed} 项，{errors} 项失败，详情请查看系统日志。",
            )
        else:
            messagebox.showinfo("配置", "所有更改已保存。")
