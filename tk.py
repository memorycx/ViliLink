import asyncio
import os.path
import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
import threading
from config import set_config, config, BASE_DIR
from dataCollection.listen import listen_messages
from repair.repair_message import parse_repair_message, delete_repair_message, delete_repair_report
from report.error import load_json_error
from report.merge import report
from report.merge_file import merge_file
from report.regenerate import re_generate_docx


# =====================================
# 全局样式配置
# =====================================
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# 定义品牌色
ACCENT_COLOR = "#3B82F6"
BG_SIDEBAR = ("#E2E8F0", "#111827")
BG_CONTENT = ("#F8FAFC", "#0F172A")
CARD_BG = ("#FFFFFF", "#1E293B")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()


        self.refresh_timer_id = None

        # 数据
        self.error_data_list = []
        self.task_data = []

        # 窗口基本设置
        self.title("SmartStream | 数据监听管理系统")
        self.geometry("1280x850")
        self.minsize(1100, 750)

        # 当前状态
        self.theme_mode = "dark"
        self.current_page = "home"
        self.nav_buttons = {}

        self.is_listening = config.IS_LISTEN

        # 配置布局网格
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 初始化组件
        self.setup_sidebar()
        self.setup_content_area()

        # 默认页面
        self.show_page("home")

    # =====================================
    # UI 布局构建
    # =====================================
    def setup_sidebar(self):
        """构建侧边栏"""
        self.sidebar = ctk.CTkFrame(self, width=260, corner_radius=0, fg_color=BG_SIDEBAR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(4, weight=1)

        # LOGO 区域
        self.logo_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.logo_container.pack(pady=(40, 40), padx=20, fill="x")

        self.logo_label = ctk.CTkLabel(
            self.logo_container,
            text="SmartStream",
            font=ctk.CTkFont(size=26, weight="bold", family="Inter")
        )
        self.logo_label.pack(side="left", padx=10)

        # 导航按钮工厂
        self.create_nav_btn("home", "🏠  主页控制台", self.show_home)
        self.create_nav_btn("tasks", "📂  待维修", self.show_tasks)
        self.create_nav_btn("error", "⚠  异常数据列", self.show_error)
        self.create_nav_btn("config", "⚙️  系统配置", self.show_config)

        # 分割线
        line = ctk.CTkFrame(self.sidebar, height=2, fg_color=("#CBD5E1", "#374151"))
        line.pack(fill="x", padx=20, pady=20)

        # 主题切换
        self.theme_btn = ctk.CTkButton(
            self.sidebar,
            text="🌙 深色模式",
            height=45,
            corner_radius=10,
            fg_color="transparent",
            border_width=1,
            text_color=("gray10", "gray90"),
            command=self.toggle_theme
        )
        self.theme_btn.pack(fill="x", padx=20, pady=10)

        # 状态指示器
        self.status_box = ctk.CTkFrame(self.sidebar, fg_color=("#F1F5F9", "#1F2937"), corner_radius=12)
        self.status_box.pack(side="bottom", fill="x", padx=20, pady=30)

        self.status_dot = ctk.CTkLabel(self.status_box, text="●", text_color="#EF4444", font=("Arial", 18))
        self.status_dot.pack(side="left", padx=(15, 5), pady=10)

        self.status_label = ctk.CTkLabel(
            self.status_box,
            text="系统状态: 待命",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.status_label.pack(side="left", pady=10)

    def create_nav_btn(self, id, text, command):
        btn = ctk.CTkButton(
            self.sidebar,
            text=text,
            height=50,
            corner_radius=10,
            anchor="w",
            font=ctk.CTkFont(size=15),
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            hover_color=("#CBD5E1", "#374151"),
            command=command
        )
        btn.pack(fill="x", padx=20, pady=5)
        self.nav_buttons[id] = btn



    def setup_content_area(self):
        """构建主体内容区"""
        self.content_canvas = ctk.CTkFrame(self, fg_color=BG_CONTENT, corner_radius=0)
        self.content_canvas.grid(row=0, column=1, sticky="nsew")

        # 容器 - 使用 grid 叠加实现页面切换
        self.home_page = ctk.CTkFrame(self.content_canvas, fg_color="transparent")
        self.tasks_page = ctk.CTkFrame(self.content_canvas, fg_color="transparent")
        self.config_page = ctk.CTkFrame(self.content_canvas, fg_color="transparent")
        self.error_page = ctk.CTkFrame(self.content_canvas, fg_color="transparent")

        self.create_home_view()
        self.create_tasks_view()
        self.create_config_view()
        self.create_error_view()

    def create_home_view(self):
        # 顶部标题栏
        header = ctk.CTkFrame(self.home_page, fg_color="transparent")
        header.pack(fill="x", padx=40, pady=(50, 30))

        ctk.CTkLabel(
            header, text="主页控制台",
            font=ctk.CTkFont(size=32, weight="bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            header, text="实时数据流监控与自动化报表中心",
            text_color="gray60", font=ctk.CTkFont(size=15)
        ).pack(anchor="w", pady=5)

        # ==================== 修改这部分 ====================
        # 卡片容器 - 使用 fill="x" 让容器撑满整行
        card_container = ctk.CTkFrame(self.home_page, fg_color="transparent")
        card_container.pack(fill="x", padx=30)

        # 配置网格列，让 3 个列权重相同（各占 1/3），实现完全等宽
        card_container.grid_columnconfigure(0, weight=1)
        card_container.grid_columnconfigure(1, weight=1)
        card_container.grid_columnconfigure(2, weight=1)

        # 快捷任务卡片 - 改用 grid 布局
        card1 = self.create_task_card(
            card_container, "数据监听", "📡",
            "实时采集 WebSocket 与 API 数据流",
            "启动服务", self.start_listen, ACCENT_COLOR
        )
        card1.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.listen_btn = card1.winfo_children()[-1]

        card2 = self.create_task_card(
            card_container, "自动化报表", "📊",
            "将监听历史转化为可视化 Excel 报表",
            "生成报告", self.create_report, "#10B981"
        )
        self.report_btn = card2.winfo_children()[-1]

        card2.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        card3 = self.create_task_card(
            card_container, "合并数据", "📌",
            "合并多人报表",
            "合并", self.merge_data, ACCENT_COLOR
        )
        card3.grid(row=0, column=2, padx=10, pady=10, sticky="ew")
        # ====================================================

        #     # 日志区域
        log_container = ctk.CTkFrame(self.home_page, fg_color=CARD_BG, corner_radius=15, border_width=1,
                                     border_color=("#E2E8F0", "#334155"))
        log_container.pack(fill="both", expand=True, padx=40, pady=30)

        log_header = ctk.CTkFrame(log_container, fg_color="transparent")
        log_header.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(log_header, text="系统日志输出", font=ctk.CTkFont(weight="bold")).pack(side="left")
        ctk.CTkButton(log_header, text="清除日志", width=80, height=25, fg_color="transparent", border_width=1,
                      command=lambda: self.log_text.delete("1.0", "end")).pack(side="right")

        self.log_text = ctk.CTkTextbox(
            log_container,
            fg_color=("#F8FAFC", "#0F172A"),
            text_color="#94A3B8",
            font=("Consolas", 13),
            corner_radius=10,
            border_spacing=10
        )
        self.log_text.pack(fill="both", expand=True, padx=15, pady=(0, 15))

    def create_task_card(self, master, title, icon, desc, btn_text, command, color):
        card = ctk.CTkFrame(master, fg_color=CARD_BG, corner_radius=20, width=380, height=220, border_width=1,
                            border_color=("#E2E8F0", "#334155"))
        # 【注意】删掉这里的 card.pack(...)，交给上面的 grid 统一管理
        card.pack_propagate(False)

        ctk.CTkLabel(card, text=icon, font=ctk.CTkFont(size=40)).pack(pady=(25, 5))
        ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=20, weight="bold")).pack()
        ctk.CTkLabel(card, text=desc, text_color="gray", font=ctk.CTkFont(size=13)).pack(pady=5)

        ctk.CTkButton(
            card, text=btn_text, fg_color=color, hover_color=color,
            width=160, height=40, corner_radius=10, font=ctk.CTkFont(weight="bold"),
            command=command
        ).pack(pady=(15, 0))

        return card  # <-- 必须加上这行

    def finish_task(self, item):
        result = messagebox.askyesno(
            "确认操作",
            f"确定已经完成文件：\n\n{item['filename']} ?"
        )

        if result:
            self.task_data.remove(item)

            delete_repair_message(item)
            delete_repair_report(item)

            self.log(f"文件已完成: {item['filename']}", "INFO")

            self.refresh_task_list()

            messagebox.showinfo("成功", "文件已删除")

    def refresh_task_list(self):
        # 清空旧组件
        for widget in self.task_container.winfo_children():
            widget.destroy()

        self.task_data = parse_repair_message()
        # 重新生成
        for item in self.task_data:
            card = ctk.CTkFrame(
                self.task_container,
                height=80,
                corner_radius=15,
                fg_color=CARD_BG,
                border_width=1,
                border_color=("#E2E8F0", "#334155")
            )
            card.pack(fill="x", pady=8, padx=5)

            # 左侧信息
            info_frame = ctk.CTkFrame(card, fg_color="transparent")
            info_frame.pack(side="left", padx=20, pady=10)

            ctk.CTkLabel(
                info_frame,
                text=item["filename"],
                font=ctk.CTkFont(size=16, weight="bold")
            ).pack(anchor="w")

            ctk.CTkLabel(
                info_frame,
                text=f"创建时间: {item['create_time']}",
                text_color="gray"
            ).pack(anchor="w")

            # 完成按钮
            finish_btn = ctk.CTkButton(
                card,
                text="完成",
                width=100,
                fg_color="#10B981",
                hover_color="#059669",
                command=lambda i=item: self.finish_task(i)
            )
            finish_btn.pack(side="right", padx=20)

    def create_tasks_view(self):
        title_frame = ctk.CTkFrame(self.tasks_page, fg_color="transparent")
        title_frame.pack(fill="x", padx=40, pady=(40, 20))

        ctk.CTkLabel(
            title_frame,
            text="待维修报表列",
            font=ctk.CTkFont(size=30, weight="bold")
        ).pack(anchor="w")

        # 列表容器
        self.task_container = ctk.CTkScrollableFrame(
            self.tasks_page,
            fg_color="transparent"
        )
        self.task_container.pack(fill="both", expand=True, padx=40, pady=10)

        self.task_data = parse_repair_message()

        self.refresh_task_list()
        self.auto_refresh()

    def create_error_view(self):
        title_frame = ctk.CTkFrame(
            self.error_page,
            fg_color="transparent"
        )
        title_frame.pack(fill="x", padx=40, pady=(40, 20))

        # 1. 标题靠左对齐 (side="left")
        ctk.CTkLabel(
            title_frame,
            text="异常数据列",
            font=ctk.CTkFont(size=30, weight="bold")
        ).pack(side="left", anchor="w")

        self.error_container = ctk.CTkScrollableFrame(
            self.error_page,
            fg_color="transparent"
        )
        self.error_container.pack(
            fill="both",
            expand=True,
            padx=40,
            pady=10
        )

        self.error_data_list = load_json_error(os.path.join(config.REPORT_PATH, "error_message"))

        # 用于存储文本框对象的字典，方便后续点击按钮时获取对应的文本
        self.textbox_registry = {}

        # -------------------------------------------------------------
        # 循环遍历：为每一条数据生成一个卡片组件
        # -------------------------------------------------------------
        for data in self.error_data_list:
            data_id = data["id"]

            # 1. 创建单条数据的卡片容器
            item_card = ctk.CTkFrame(
                self.error_container,
                fg_color=("#F2F2F2", "#1E293B"),
                corner_radius=10
            )
            item_card.pack(fill="x", pady=8, ipady=10, padx=5)

            # 依然划分三列：左侧复合信息(0) -> 占 35% | 文本框(1) -> 占 50% | 按钮(2) -> 占 15%
            item_card.grid_columnconfigure(0, weight=35)
            item_card.grid_columnconfigure(1, weight=50)
            item_card.grid_columnconfigure(2, weight=15)

            # 2. 左侧复合信息列 (采用横向排列布局)
            info_block = ctk.CTkFrame(item_card, fg_color="transparent")
            info_block.grid(row=0, column=0, padx=(20, 10), pady=10, sticky="ew")

            # (1) 错误原因
            reason_label = ctk.CTkLabel(
                info_block,
                text=data["reason"],
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=("#EF4444", "#F87171"),
                anchor="w"
            )
            reason_label.pack(side="left", padx=(0, 25))

            # (2) 附加字段一：群号
            group_val = data.get("group_id", "未知群号")
            group_label = ctk.CTkLabel(
                info_block,
                text=f" 群: {group_val}",
                font=ctk.CTkFont(size=11),
                text_color="gray",
                anchor="w"
            )
            group_label.pack(side="left", padx=(0, 15))

            # (3) 附加字段二：时间
            time_val = data.get("time", "未知时间")
            time_label = ctk.CTkLabel(
                info_block,
                text=f"{time_val}",
                font=ctk.CTkFont(size=11),
                text_color="gray",
                anchor="w"
            )
            time_label.pack(side="left")

            # 3. 字段二：可编辑的文本输入框
            data_entry = ctk.CTkEntry(
                item_card,
                font=ctk.CTkFont(size=13)
            )
            data_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
            data_entry.insert(0, data["content"])

            # 将输入框对象存入字典
            self.textbox_registry[data_id] = data_entry

            # 4. 字段三：专属操作按钮
            action_btn = ctk.CTkButton(
                item_card,
                text="确认修改",
                width=100,
                fg_color=("#3B82F6", "#2563EB"),
                hover_color=("#1D4ED8", "#1E40AF"),
                command=lambda d_id=data_id: self.on_save_clicked(d_id)
            )
            action_btn.grid(row=0, column=2, padx=(10, 20), pady=10, sticky="e")

    # -------------------------------------------------------------
    # 按钮点击后的业务逻辑处理
    # -------------------------------------------------------------
    def on_save_clicked(self, data_id):
        # 1. 根据 ID 找到对应的输入框组件
        target_entry = self.textbox_registry.get(data_id)

        if target_entry:
            # 2. 获取用户在输入框中修改后的最新文本
            updated_text = target_entry.get()
            re_generate_docx(data_id, updated_text, self.log)
        else:
            re_generate_docx(data_id, "", self.log)

        # 这里需要刷新界面
        self.refresh_error_list()

    def create_config_view(self):
        # 简单表单布局
        title_frame = ctk.CTkFrame(self.config_page, fg_color="transparent")
        title_frame.pack(fill="x", padx=40, pady=(50, 30))
        ctk.CTkLabel(title_frame, text="配置中心", font=ctk.CTkFont(size=32, weight="bold")).pack(anchor="w")

        form_card = ctk.CTkFrame(self.config_page, fg_color=CARD_BG, corner_radius=20, border_width=1,
                                 border_color=("#E2E8F0", "#334155"))
        form_card.pack(fill="x", padx=40, pady=10)

        configs = [
            ("TOKEN_WEBSOCKET", "访问令牌", config.TOKEN_WEBSOCKET),
            ("URL_WEBSOCKET", "连接地址", config.URL_WEBSOCKET),
            ("TOKEN_SEND", "发送令牌", config.TOKEN_SEND),
            ("URL_SEND", "发送地址", config.URL_SEND),
            ("SAVE_ROOT_DIR", "保存根目录", config.SAVE_ROOT_DIR),
            ("LOCAL_IMAGES_DIR", "本地QQ保存图片目录", config.LOCAL_IMAGES_DIR),
            # ("关键词过滤", "多个关键词请用英文逗号隔开", "error, warning, critical")
        ]

        self.entries = {}
        for i, (name, detail, placeholder) in enumerate(configs):
            row = ctk.CTkFrame(form_card, fg_color="transparent")
            row.pack(fill="x", padx=30, pady=15)

            lbl_info = ctk.CTkFrame(row, fg_color="transparent")
            lbl_info.pack(side="left")
            ctk.CTkLabel(lbl_info, text=name, font=ctk.CTkFont(size=15, weight="bold")).pack(anchor="w")
            ctk.CTkLabel(lbl_info, text=detail, font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w")

            entry = ctk.CTkEntry(row, width=400, height=40, corner_radius=8, placeholder_text=placeholder)
            entry.pack(side="right", padx=10)
            self.entries[name] = entry

        save_btn = ctk.CTkButton(
            self.config_page, text="确认并保存更改",
            height=50, width=250, corner_radius=12,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self.save_config
        )
        save_btn.pack(pady=40)

    def refresh_error_list(self):
        """刷新异常数据列表"""

        error_file_path = os.path.join(config.REPORT_PATH, "error_message")
        self.error_data_list = load_json_error(error_file_path)

        for widget in self.error_container.winfo_children():
            widget.destroy()

        # 3.重要：清空文本框组件映射字典，防止内存残留与修改错位
        self.textbox_registry.clear()

        # 4.强制更新界面布局渲染，释放 Tkinter 资源
        self.update_idletasks()

        # 5. 重新循环渲染数据卡片
        for data in self.error_data_list:
            data_id = data["id"]

            # 创建单条数据的卡片容器
            item_card = ctk.CTkFrame(
                self.error_container,
                fg_color=("#F2F2F2", "#1E293B"),
                corner_radius=10
            )
            item_card.pack(fill="x", pady=8, ipady=10, padx=5)

            # 划分三列占比
            item_card.grid_columnconfigure(0, weight=35)
            item_card.grid_columnconfigure(1, weight=50)
            item_card.grid_columnconfigure(2, weight=15)

            # 左侧复合信息列
            info_block = ctk.CTkFrame(item_card, fg_color="transparent")
            info_block.grid(row=0, column=0, padx=(20, 10), pady=10, sticky="ew")

            # 错误原因
            reason_label = ctk.CTkLabel(
                info_block,
                text=data["reason"],
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=("#EF4444", "#F87171"),
                anchor="w"
            )
            reason_label.pack(side="left", padx=(0, 25))

            # 群号
            group_val = data.get("group_id", "未知群号")
            group_label = ctk.CTkLabel(
                info_block,
                text=f" 群: {group_val}",
                font=ctk.CTkFont(size=11),
                text_color="gray",
                anchor="w"
            )
            group_label.pack(side="left", padx=(0, 15))

            # 时间转换（如果是时间戳，自动转换为秒级格式）
            raw_time = data.get("time", "未知时间")
            if isinstance(raw_time, (int, float)) and raw_time > 0:
                import datetime
                time_val = datetime.datetime.fromtimestamp(raw_time).strftime('%Y-%m-%d %H:%M:%S')
            else:
                time_val = str(raw_time)

            time_label = ctk.CTkLabel(
                info_block,
                text=f"{time_val}",
                font=ctk.CTkFont(size=11),
                text_color="gray",
                anchor="w"
            )
            time_label.pack(side="left")

            # 可编辑文本框
            data_entry = ctk.CTkEntry(
                item_card,
                font=ctk.CTkFont(size=13)
            )
            data_entry.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
            data_entry.insert(0, data["content"])

            # 重新注册映射关系
            self.textbox_registry[data_id] = data_entry

            # 专属操作按钮
            action_btn = ctk.CTkButton(
                item_card,
                text="确认修改",
                width=100,
                fg_color=("#3B82F6", "#2563EB"),
                hover_color=("#1D4ED8", "#1E40AF"),
                command=lambda d_id=data_id: self.on_save_clicked(d_id)
            )
            action_btn.grid(row=0, column=2, padx=(10, 20), pady=10, sticky="e")

    # =====================================
    # 逻辑功能
    # =====================================
    def show_page(self, page_id):
        # 切换页面显示
        self.home_page.pack_forget()
        self.tasks_page.pack_forget()
        self.error_page.pack_forget()
        self.config_page.pack_forget()

        if page_id == "home":
            self.home_page.pack(fill="both", expand=True)

        elif page_id == "tasks":
            self.tasks_page.pack(fill="both", expand=True)

        elif page_id == "error":
            self.error_page.pack(fill="both", expand=True)

        else:
            self.config_page.pack(fill="both", expand=True)

        # 更新导航栏状态
        for id, btn in self.nav_buttons.items():
            if id == page_id:
                btn.configure(fg_color=ACCENT_COLOR, text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color=("gray10", "gray90"))

    def show_home(self):
        self.show_page("home")

    def show_config(self):
        self.show_page("config")

    def show_tasks(self):
        self.show_page("tasks")

    def show_error(self):
        self.show_page("error")

    def log(self, message, level="INFO"):
        time_str = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert("end", f"[{time_str}] ", "time")
        self.log_text.insert("end", f"[{level}] ", level)
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")

    def toggle_theme(self):
        if self.theme_mode == "dark":
            ctk.set_appearance_mode("light")
            self.theme_mode = "light"
            self.theme_btn.configure(text="☀️ 白天模式")
            self.content_canvas.configure(fg_color=BG_CONTENT[0])
        else:
            ctk.set_appearance_mode("dark")
            self.theme_mode = "dark"
            self.theme_btn.configure(text="🌙 深色模式")
            self.content_canvas.configure(fg_color=BG_CONTENT[1])

    def start_listen(self):
        if not self.is_listening:
            # ---------------------------
            # 情况 A: 启动服务
            # ---------------------------
            self.is_listening = True
            set_config("IS_LISTEN", "True", self.log)

            # 1. 更新系统状态栏
            self.status_dot.configure(text_color="#10B981")
            self.status_label.configure(text="系统状态：监听中")

            # 2. 核心联动：禁用“生成报告”按钮，并改变监听按钮文字
            self.report_btn.configure(state="disabled", fg_color="gray", hover_color="gray")
            self.listen_btn.configure(text="停止服务", fg_color="#EF4444", hover_color="#DC2626")

            # 3. 异步启动
            def run_async_loop():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                # 注意：如果你的 listen_messages 支持通过全局变量或传入 self 来判断是否退出死循环，效果会更好
                loop.run_until_complete(listen_messages(self.log))

            threading.Thread(target=run_async_loop, daemon=True).start()
            messagebox.showinfo("提示", "监听线程已在后台启动，“生成报告”功能已锁定。")
            self.log("数据监听服务已启动...", "INFO")

        else:
            # ---------------------------
            # 情况 B: 关闭服务
            # ---------------------------
            self.is_listening = False

            # 1. 恢复状态栏
            self.status_dot.configure(text_color="#EF4444")
            self.status_label.configure(text="系统状态：待命")

            # 2. 核心联动：恢复“生成报告”按钮，并还原监听按钮文字
            self.report_btn.configure(state="normal", fg_color="#10B981", hover_color="#059669")
            self.listen_btn.configure(text="启动服务", fg_color=ACCENT_COLOR, hover_color=ACCENT_COLOR)

            messagebox.showinfo("提示", "监听服务已关闭，“生成报告”功能已解锁。")
            self.log("数据监听服务已停止。", "WARNING")

    def create_report(self):
        self.log("正在分析历史缓存数据...", "INFO")
        self.log("报表引擎启动:", "INFO")

        def run_async_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            target_path = BASE_DIR / 'chat_logs'
            loop.run_until_complete(report(target_path, self.log))

        threading.Thread(target=run_async_loop, daemon=True).start()
        messagebox.showinfo("成功", "报表已生成并导出。")

        self.refresh_error_list()

    def save_config(self):
        for name, entry in self.entries.items():
            if entry.get():
                set_config(name, entry.get(), self.log)
                self.log(f"{name}: {entry.get()}", "INFO")

        self.log("系统配置已更新", "WARNING")
        messagebox.showinfo("配置", "所有更改已生效。")

    def merge_data(self):
        self.log("正在合并数据...", "WARNING")
        merge_file()
        self.log("数据合并完成", "WARNING")

    def auto_refresh(self):
        # 1. 【核心修复】如果之前已经有定时器在运行，先将它取消，防止定时器无限叠加
        if self.refresh_timer_id is not None:
            self.after_cancel(self.refresh_timer_id)
            self.refresh_timer_id = None

        # 2. 立刻执行一次刷新，更新界面数据
        self.refresh_task_list()
        self.refresh_timer_id = self.task_container.after(5000, self.auto_refresh)
