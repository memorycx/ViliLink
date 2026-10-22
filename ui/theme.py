"""界面配色与主题。"""

from __future__ import annotations

import customtkinter as ctk

ACCENT_COLOR = "#3B82F6"
SUCCESS_COLOR = "#10B981"
DANGER_COLOR = "#EF4444"
WARNING_COLOR = "#F59E0B"

BG_SIDEBAR = ("#E2E8F0", "#111827")
BG_CONTENT = ("#F8FAFC", "#0F172A")
CARD_BG = ("#FFFFFF", "#1E293B")
ERROR_CARD_BG = ("#F2F2F2", "#1E293B")
BORDER_COLOR = ("#E2E8F0", "#334155")
NAV_TEXT = ("gray10", "gray90")
NAV_HOVER = ("#CBD5E1", "#374151")

LOG_COLORS = {
    "INFO": "#94A3B8",
    "SUCCESS": "#34D399",
    "WARNING": "#FBBF24",
    "ERROR": "#F87171",
}


def configure_theme() -> None:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
