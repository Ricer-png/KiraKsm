import threading
import queue
import json
import os
import tkinter as tk
from PIL import Image, ImageTk
from tkinter import scrolledtext, messagebox, ttk
from card_scraper import run_scraper
from band_scraper import run_scraper_band
from area_scraper import run_scraper_area
from audio_to_list import run_A_to_Z
from get_path import resource_path

class BestdoriScraperUI:
    def __init__(self):
        self.log_queue = queue.Queue()
        self.progress_queue = queue.Queue()
        # 用于通知爬虫线程终止
        self.stop_event = threading.Event()
        self.wav_event = threading.Event()

        self.root = tk.Tk()
        self.root.title("KiraKsm v1.0.1")

        self.window_width = 1000
        self.window_height = 700
        # 获取屏幕尺寸以计算布局参数，使窗口居中
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x_cordinate = int((screen_width/2) - (self.window_width/2))
        y_cordinate = int((screen_height/2) - (self.window_height/2))
        self.root.geometry(f"{self.window_width}x{self.window_height}+{x_cordinate}+{y_cordinate}")
        self.root.resizable(False, False)  # 禁止调整窗口大小
        self.root.attributes('-fullscreen', False)  # 禁止全屏
        self.root.iconbitmap(resource_path(os.path.join("source", "ksm.ico")))        

        # 加载背景图片，并生成PhotoImage
        bg_pil = Image.open(resource_path(os.path.join("source", "bgd1.png"))).convert("RGBA").resize((self.window_width, self.window_height))
        self.bg_tk = ImageTk.PhotoImage(bg_pil)
        bg_pil2 = Image.open(resource_path(os.path.join("source", "bgd2.png"))).convert("RGBA").resize((self.window_width, self.window_height))
        self.bg_tk2 = ImageTk.PhotoImage(bg_pil2)
        bg_pil3 = Image.open(resource_path(os.path.join("source", "bgd3.png"))).convert("RGBA").resize((self.window_width, self.window_height))
        self.bg_tk3 = ImageTk.PhotoImage(bg_pil3)
        bg_pil4 = Image.open(resource_path(os.path.join("source", "bgd4.png"))).convert("RGBA").resize((self.window_width, self.window_height))
        self.bg_tk4 = ImageTk.PhotoImage(bg_pil4)

        # 创建Canvas作为背景承载
        self.canvas = tk.Canvas(self.root, width=1000, height=700)
        self.canvas.pack(fill="both", expand=True)
        self.bg_canvas = self.canvas.create_image(0, 0, image=self.bg_tk, anchor="nw")

        # 顶部页面切换单选按钮（放在Canvas外层或用place定位在Canvas上）
        self.page_var = tk.StringVar(value="scraper")
        self.scraper_radio = tk.Radiobutton(self.root, text="收集", variable=self.page_var, value="scraper", font=("微软雅黑", 10), command=self.switch_page)
        self.new_radio = tk.Radiobutton(self.root, text="处理", variable=self.page_var, value="new", font=("微软雅黑", 10), command=self.switch_page)
        self.scraper_radio.place(x=0, y=0)
        self.new_radio.place(x=50, y=0)

        # 创建一个容器 Frame，用于放置不同的页面
        self.page_container = tk.Frame(self.canvas, width=750, height=380)
        # 将容器嵌入Canvas中，居中显示
        self.canvas.create_window(500, 330, window=self.page_container, anchor="center")

        # 在容器内创建两个页面Frame
        self.scraper_frame = tk.Frame(self.page_container, bg="#CFFFFF")
        self.new_page_frame = tk.Frame(self.page_container, bg="#FFCFFF")

        # 初始化
        self.init_scraper_page()
        self.init_new_page()
        self.scraper_frame.pack(fill="both", expand=True)
        self.update_log()

    def init_scraper_page(self):
        # 顶部输入框、按钮、乐队或卡面选择开关
        self.top_frame = tk.Frame(self.scraper_frame, bg="#DFFFFF", bd=2, relief="groove")
        self.top_frame.pack(pady=5)

        self.label = tk.Label(self.top_frame, text="角色名称", font=("微软雅黑", 16), bg="#DFFFFF")
        self.label.grid(row=0, column=0, padx=5, pady=5)
        self.entry = tk.Entry(self.top_frame, font=("微软雅黑", 16), bg="#EFFFFF", width=15, bd=2)
        self.entry.grid(row=0, column=1, padx=5, pady=5)
        
        self.scraper_type_var = tk.StringVar(value="card")
        self.card_scraper_radio = tk.Radiobutton(self.top_frame, text="卡面", variable=self.scraper_type_var, value="card", font=("微软雅黑", 12), bg="#DFFFFF", command=self.switch_scraper)
        self.band_scraper_radio = tk.Radiobutton(self.top_frame, text="乐队", variable=self.scraper_type_var, value="band", font=("微软雅黑", 12), bg="#DFFFFF", command=self.switch_scraper)
        self.area_scraper_radio = tk.Radiobutton(self.top_frame, text="区域", variable=self.scraper_type_var, value="area", font=("微软雅黑", 12), bg="#DFFFFF", command=self.switch_scraper)
        self.card_scraper_radio.grid(row=0, column=2, padx=0, pady=5)
        self.band_scraper_radio.grid(row=0, column=3, padx=0, pady=5)
        self.area_scraper_radio.grid(row=0, column=4, padx=0, pady=5)

        self.extension_var = tk.StringVar(value="mp3")
        self.mp3_file = tk.Radiobutton(self.top_frame, text="mp3", variable=self.extension_var, value="mp3", font=("微软雅黑", 12), bg="#BFFFFF", command=self.set_mp3orwav)
        self.wav_file = tk.Radiobutton(self.top_frame, text="wav", variable=self.extension_var, value="wav", font=("微软雅黑", 12), bg="#BFFFFF", command=self.set_mp3orwav)
        self.mp3_file.grid(row=0, column=5, padx=0, pady=5)
        self.wav_file.grid(row=0, column=6, padx=0, pady=5)
        
        self.button = tk.Button(self.top_frame, text="开始收集", font=("微软雅黑", 14, "bold"), bg="#4CAF50", fg="white", command=self.start_scraper)
        self.button.grid(row=0, column=7, padx=5, pady=5)
        self.stop_button = tk.Button(self.top_frame, text="暂停", font=("微软雅黑", 14, "bold"), bg="#F44336", fg="white", command=self.stop_scraper)
        self.stop_button.grid(row=0, column=8, padx=5, pady=5)
        self.root.bind("<Return>", lambda event: self.button.invoke())
        self.stop_button.config(state=tk.DISABLED)

        # 信息显示窗口
        self.log_frame = tk.Frame(self.scraper_frame, bg="#F0F0F0", bd=2, relief="sunken")
        self.log_frame.pack(pady=0)
        self.log_text = scrolledtext.ScrolledText(self.log_frame, font=("微软雅黑", 14), wrap="word", bg="#EFFFFF", height=15, width=70)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.config(state=tk.DISABLED)

        # 进度条
        self.progress_bar = ttk.Progressbar(self.scraper_frame, length=788, mode="determinate")
        self.progress_bar.pack(pady=5)

    def init_new_page(self):
        # R1
        self.new_top_frame = tk.Frame(self.new_page_frame, bg="#FFDFFF", bd=2)
        self.new_top_frame.pack(pady=0)
        self.label1 = tk.Label(self.new_top_frame, text="目标路径", font=("微软雅黑", 16), bg="#FFDFFF")
        self.label1.grid(row=0, column=0, padx=4, pady=5)
        self.path_entry = tk.Entry(self.new_top_frame, font=("微软雅黑", 16), bg="#FFEFFF", width=44, bd=2)
        self.path_entry.grid(row=0, column=1, padx=4, pady=5)
        # R2
        self.new_top_frame2 = tk.Frame(self.new_page_frame, bg="#FFDFFF", bd=2)
        self.new_top_frame2.pack(pady=0)
        self.label2 = tk.Label(self.new_top_frame2, text="角色名称", font=("微软雅黑", 16), bg="#FFDFFF")
        self.label2.grid(row=0, column=0, padx=4, pady=3)
        self.name_entry = tk.Entry(self.new_top_frame2, font=("微软雅黑", 16), bg="#FFEFFF", width=28, bd=2)
        self.name_entry.grid(row=0, column=1, padx=4, pady=3)

        self.mp3_file = tk.Radiobutton(self.new_top_frame2, text="mp3", variable=self.extension_var, value="mp3", font=("微软雅黑", 12), bg="#FFDFFF", command=self.set_mp3orwav)
        self.wav_file = tk.Radiobutton(self.new_top_frame2, text="wav", variable=self.extension_var, value="wav", font=("微软雅黑", 12), bg="#FFDFFF", command=self.set_mp3orwav)
        self.mp3_file.grid(row=0, column=2, padx=0, pady=5)
        self.wav_file.grid(row=0, column=3, padx=0, pady=5)
        
        self.audio2list_button = tk.Button(self.new_top_frame2, text="开始", font=("微软雅黑", 14, "bold"), bg="#2196F3", fg="white", command=self.start_audio2list)
        self.audio2list_button.grid(row=0, column=4, padx=4, pady=3)
        # R3
        self.new_message_frame = tk.Frame(self.new_page_frame, bg="#F0F0F0", bd=2, relief="sunken")
        self.new_message_frame.pack(pady=5, fill="both", expand=True)
        self.new_message_text = scrolledtext.ScrolledText(self.new_message_frame, font=("微软雅黑", 14), wrap="word", bg="#FFEFFF", height=12, width=55)
        self.new_message_text.pack(fill="both", expand=True)
        self.new_message_text.config(state=tk.DISABLED)

    def switch_page(self):
        current_wav_flag = self.extension_var.get()
        # 根据选择切换页面及背景图片
        if self.page_var.get() == "scraper":
            self.new_page_frame.pack_forget()  # 隐藏新页面
            self.scraper_frame.pack(fill="both", expand=True)
            self.canvas.itemconfig(self.bg_canvas, image=self.bg_tk)
            self.button.config(state=tk.NORMAL)
            self.extension_var.set(current_wav_flag)
        else:
            self.scraper_frame.pack_forget()  # 隐藏主页面
            self.new_page_frame.pack(fill="both", expand=True)
            self.canvas.itemconfig(self.bg_canvas, image=self.bg_tk3)
            self.button.config(state=tk.DISABLED)
            self.extension_var.set(current_wav_flag)
            self.log_queue.put("这是为GPT-SoVITS定制的功能\n\n\"目标路径\"指的是: \"训练模型时, 这些音频资源所在的文件夹绝对路径\"\n\n如: d:\\workspace\\source\\aya\\aya_sudio\n\n如果不打算移动上一步爬取的资源, 可以不填\n\n角色名为必填项, 用于获取资源当前所在的地址\n\n------------------------------------------")

    def freeze_radios(self):
        self.scraper_radio.config(state=tk.DISABLED)
        self.new_radio.config(state=tk.DISABLED)
        self.card_scraper_radio.config(state=tk.DISABLED)
        self.band_scraper_radio.config(state=tk.DISABLED)
        self.area_scraper_radio.config(state=tk.DISABLED)
        self.mp3_file.config(state=tk.DISABLED)
        self.wav_file.config(state=tk.DISABLED)

    def unfreeze_radios(self):
        self.scraper_radio.config(state=tk.NORMAL)
        self.new_radio.config(state=tk.NORMAL)
        self.card_scraper_radio.config(state=tk.NORMAL)
        self.band_scraper_radio.config(state=tk.NORMAL)
        self.area_scraper_radio.config(state=tk.NORMAL)
        self.mp3_file.config(state=tk.NORMAL)
        self.wav_file.config(state=tk.NORMAL)

    def switch_scraper(self):
        # 根据选择切换背景图片
        scraper_type = self.scraper_type_var.get()
        if scraper_type == "card":
            self.canvas.itemconfig(self.bg_canvas, image=self.bg_tk)
        elif scraper_type == "band":
            self.canvas.itemconfig(self.bg_canvas, image=self.bg_tk2)
        elif scraper_type == "area":
            self.canvas.itemconfig(self.bg_canvas, image=self.bg_tk4)

    def set_mp3orwav(self):
        flag = self.extension_var.get()
        if flag == "mp3":
            self.wav_event.clear()
        elif flag == "wav":
            self.wav_event.set()

    def count_files_in_leaf_folders(self, root_dir):
        result = {}
        base_path = os.path.abspath(root_dir)
        for root, dirs, files in os.walk(root_dir):
            if not dirs:
                rel_path = os.path.relpath(root, base_path)
                result[rel_path] = len(files)
        return result

    def start_scraper(self):
        target_name = self.entry.get().strip()
        if not target_name:
            self.log_queue.put("请输入常见角色名, 更多提示可输入 help 查询")
            return
        elif target_name == "help":
            self.log_queue.put("nickname : 全部可识别角色名")
            self.log_queue.put("pwd : 工作目录")
            self.log_queue.put("count : 统计目录下文件数量")
            self.log_queue.put("tips : 作者想说的话")
            return
        elif target_name == "tips":
            self.log_queue.put("\n-----------------------------------------------------------------------------------------")
            self.log_queue.put("1.本爬虫数据来自bestdori，为了不给网站运营方造成困扰，加入了很多time.sleep()，并且禁止并发。如果您认为太慢，请从 https://github.com/Ricer-png/KiraKsm 获取源码后自主修改。另外，请不要喷我代码质量差......")
            self.log_queue.put("\n2..wav格式文件为.mp3文件转码得到，音质相同，体积扩大5倍。尽量选择下载.mp3文件。")
            self.log_queue.put("\n3.下载.mp3格式文件后，再下载.wav格式文件，会从上次下载暂停处开始下载，反之同理。如果想从头下载，请删除角色名目录下的.json文件。")
            self.log_queue.put("\n4.本程序仅供学习交流使用，禁止商用。感谢您的支持和理解。")
            self.log_queue.put("\n                                                                                 by 花笑川乐奈")
            self.log_queue.put("\n-----------------------------------------------------------------------------------------")
            return
        elif target_name == "count":
            stats = self.count_files_in_leaf_folders(".")
            for folder, count in sorted(stats.items()):
                self.log_queue.put(f"• {folder}:     {count}    个文件")
            return
        elif target_name == "pwd":
            self.log_queue.put(resource_path(""))
            return
        elif target_name == "nickname":
            reverse_map = {}
            try:
                with open(resource_path("characters.json"), "r", encoding="utf-8") as f:
                    character_map = json.load(f)
                    for nick, names in character_map.items():
                        official_name = names[0]
                        if official_name not in reverse_map:
                            reverse_map[official_name] = []
                        reverse_map[official_name].append(nick)      
                for official_name, nick in reverse_map.items():
                    self.log_queue.put(f"{official_name}:    {'    '.join(nick)}")
                return

            except FileNotFoundError:
                self.log_queue.put("错误: 未找到角色映射文件 characters.json")
                return
        
        # 每次启动前重置停止标志
        self.stop_event.clear()
        self.button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.freeze_radios()

        scraper_type = self.scraper_type_var.get()
        if scraper_type == "card":
            scraper_func = run_scraper
        elif scraper_type == "band":
            scraper_func = run_scraper_band
        elif scraper_type == "area":
            scraper_func = run_scraper_area
        else:
            self.button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.unfreeze_radios()
            return
        threading.Thread(target=self.run_scraper_thread, args=(scraper_func, target_name), daemon=True).start()

    def run_scraper_thread(self, scraper_func, target_name):
        try:
            scraper_func(target_name, self.log_queue, self.progress_queue, self.stop_event, self.wav_event)
        finally:
            self.button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.unfreeze_radios()

    def stop_scraper(self):
        # 设置停止标志，让爬虫线程主动退出
        self.stop_event.set()
        self.log_queue.put("暂停收集, 下次会从暂停章节开头处重新下载哦")

    def start_audio2list(self):
        target_path = self.path_entry.get().strip()
        target_name = self.name_entry.get().strip()
        if not target_name:
            return
        self.audio2list_button.config(state=tk.DISABLED)
        threading.Thread(target=self.run_audio2list_thread, args=(target_name, target_path,), daemon=True).start()

    def run_audio2list_thread(self, target_name, target_path):
        try:
            run_A_to_Z(target_name, self.log_queue, target_path, self.wav_event)
        finally:
            self.audio2list_button.config(state=tk.NORMAL)

    def update_log(self):
        while not self.log_queue.empty():
            message = self.log_queue.get()
            # 根据当前页面切换日志输出位置
            if self.page_var.get() == "scraper":
                self.log_text.config(state=tk.NORMAL)
                self.log_text.insert(tk.END, message + "\n")
                self.log_text.config(state=tk.DISABLED)
                self.log_text.see(tk.END)
            else:
                self.new_message_text.config(state=tk.NORMAL)
                self.new_message_text.insert(tk.END, message + "\n")
                self.new_message_text.config(state=tk.DISABLED)
                self.new_message_text.see(tk.END)
        # 进度条        
        while not self.progress_queue.empty():
            progress = self.progress_queue.get()
            self.progress_bar["value"] = progress * 100
        self.root.after(100, self.update_log)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = BestdoriScraperUI()
    app.run()
