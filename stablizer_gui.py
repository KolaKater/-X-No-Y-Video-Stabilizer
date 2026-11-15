# -*- coding: utf-8 -*-
"""
stablizer_gui.py - 多语言界面, 只做左右防抖
按钮: 文件 / 文件夹 / 开始 / 暂停 / 取消 / 帧率 / 关于 / 脸书
- 文件: 打开一个或多个视频
- 文件夹: 选择包含视频或帧序列的文件夹
- 文件列表中, 不同文件夹的帧序列不能同时存在 (会弹窗阻止)
- 图片统一 jpg, 质量 95; 视频统一 mp4, x265, crf 18 (约 95 质量)
- 视频 fps 由原视频决定; 帧序列可选择保存帧 或 保存成 mp4, fps 选项见 FPS_COMBO
- 视频输出: 原名_1910x1080_stablized.mp4 (按实际新尺寸)
- 帧序列保存帧: 在帧序列文件夹外面生成 文件夹名_stablized, 帧名 + _stablized.jpg
- 帧序列保存成 mp4: 在外面生成 文件夹名_fps_stablized.mp4
相对路径运行: 双击 Lanch_stablizer_gui.bat
"""
import os, sys, json, threading, queue, time, webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

if getattr(sys, "frozen", False):
    HERE = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))  # 资源目录
    APP_DIR = Path(sys.executable).resolve().parent  # 可写目录 (配置)
else:
    HERE = Path(__file__).resolve().parent
    APP_DIR = HERE
sys.path.insert(0, str(HERE))
from vid_stablizer import (debug_log, _NO_WINDOW, stabilize_video_file, stabilize_frames_opencv_x_only,
    stabilize_frames_ffmpeg_x_only, list_frames, get_video_info, crop_w_for_x_only,
    output_frames_dir, IMAGE_EXTS)

VIDEO_EXTS = {".mp4",".mov",".mkv",".avi",".webm",".m4v",".wmv",".flv",".mpg",".mpeg",".m2ts",".mts",".ts",".3gp",".3g2",".asf",".f4v",".rm",".rmvb",".vob",".ogv",".mxf"}
IMAGE_EXTS = {".jpg",".jpeg",".png",".bmp",".tif",".tiff",".webp",".gif",".heic",".heif",".avif",".jxl",".ppm",".pgm",".tga"}
FPS_OPTIONS = ["23.976fps", "24fps", "25fps", "29.97fps", "30fps", "50fps", "60fps", "120fps"]

def _load_langs():
    import json as _json
    here = Path(__file__).resolve().parent
    candidates = [here / "bin" / "stablizer_languages.json", here / "stablizer_languages.json", APP_DIR / "bin" / "stablizer_languages.json"]
    for c in candidates:
        try:
            if c.exists():
                return _json.loads(c.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"load langs failed {c}: {e}")
    return {}
LANGS = _load_langs()
# Fallback minimal if json missing
if not LANGS:
    LANGS = {"中文": {"title":"视频左右防抖","file":"文件","folder":"文件夹","start":"开始","pause":"暂停","cancel":"取消","fps":"帧率","about":"关于","facebook":"脸书","method":"方案","method1":"方案一","method2":"方案二","save_mode":"帧序列输出","save_frames":"保存帧","save_mp4":"保存成 MP4","smoothing":"平滑强度","list":"文件列表","status":"状态","progress":"进度","lang":"语言","clear":"清空列表","remove":"移除选中","about_text":"X No Y Video Stabilizer for Windows\nOnly X-axis is stabilized, Y stays untouched.\n\nhttps://github.com/KolaKater/-X-No-Y-Video-Stabilizer\n© 2026 Tony Lin","mixed_frames":"mixed","done":"全部完成","paused":"已暂停","cancelled":"已取消","add_video":"已添加视频","add_frames":"已添加帧序列","no_task":"请先添加","confirm_clear":"清空列表?","running":"Running....","done_prefix":"Done","click_hint":"单击打开文件夹"}}
FACEBOOK_URL = "https://www.facebook.com/100000242772138"
GITHUB_URL = "https://github.com/KolaKater/-X-No-Y-Video-Stabilizer"  # X No Y Video Stabilizer for Windows, © 2026
CONFIG_PATH = APP_DIR / "bin" / "stablizer_gui_config.json"
CONFIG_DEFAULTS = {"lang": "中文", "method": "ffmpeg", "fps": "24fps", "save_mode": "mp4", "smoothing": 30, "output_size": "original", "ref": "global", "warp": "off"}

class App:
    def __init__(self, root):
        self.root = root
        self.lang_name = tk.StringVar(value="中文")
        self.tasks = []  # list of dict {type: video|frames, path: Path}
        self.frames_folder = None  # 当前帧序列所在文件夹, 用于防混放
        self.paused = False
        self.cancelled = False
        self.running = False
        self.q = queue.Queue()
        self._status_full = ""
        self._scroll_pos = 0
        self._scroll_dir = 1
        debug_log("GUI started")
        self._cfg = self._load_config()
        self.build_ui()
        self._apply_config()
        self._bind_save()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(200, self.poll_queue)
        self.root.after(300, self._tick_scroll)
        self.setup_drag_drop()

    def T(self, k): return LANGS[self.lang_name.get()].get(k, k)

    def _load_config(self):
        try:
            if CONFIG_PATH.exists():
                data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    cfg = dict(CONFIG_DEFAULTS); cfg.update(data); return cfg
        except Exception as e:
            debug_log(f"load config failed: {e}", "warning")
        return dict(CONFIG_DEFAULTS)

    def _save_config(self, *_a):
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {"lang": self.lang_name.get(), "method": self.method_var.get(), "fps": self.fps_var.get(),
                    "save_mode": self.save_var.get(), "smoothing": int(self.smooth_var.get()),
                    "output_size": self.output_size_var.get(), "ref": self.ref_var.get(), "warp": self.warp_var.get()}
            CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            debug_log(f"save config failed: {e}", "warning")

    def _apply_config(self):
        try:
            c = self._cfg
            if c.get("lang") in LANGS: self.lang_name.set(c["lang"])
            if c.get("method") in ("ffmpeg", "opencv"): self.method_var.set(c["method"])
            if c.get("fps") in FPS_OPTIONS: self.fps_var.set(c["fps"])
            if c.get("save_mode") in ("frames", "mp4"): self.save_var.set(c["save_mode"])
            try: self.smooth_var.set(int(c.get("smoothing", 30)))
            except Exception: pass
            if c.get("output_size") in ("cropped", "original"): self.output_size_var.set(c["output_size"])
            if c.get("ref") in ("global", "foreground", "background"): self.ref_var.set(c["ref"])
            if c.get("warp") in ("off", "mesh_light", "mesh_medium", "mesh_heavy"): self.warp_var.set(c["warp"])
        except Exception as e:
            debug_log(f"apply config failed: {e}", "warning")

    def _bind_save(self):
        for var in (self.lang_name, self.method_var, self.fps_var, self.save_var, self.smooth_var, self.output_size_var, self.ref_var, self.warp_var):
            try: var.trace_add("write", lambda *a: self._save_config())
            except Exception: pass

    def _on_close(self):
        self._save_config()
        self.root.destroy()

    def build_ui(self):
        self.root.title(self.T("title")); self.root.geometry("860x620")
        self.lang_name.trace_add("write", lambda *a: self.refresh_texts())
        # 上排 (原下排互换上来): 左 [关于][脸书]  中间撑开  右 [移除选中][清空列表]
        _BW, _BH = 13, 2
        btns = tk.Frame(self.root); btns.pack(fill="x", padx=10, pady=(15, 0))  # 上面留 5, 与标题栏分开
        self.b_about = tk.Button(btns, text=self.T("about"), width=_BW, height=_BH, command=self.show_about); self.b_about.pack(side="left", padx=3)
        self.b_fb = tk.Button(btns, text=self.T("facebook"), width=_BW, height=_BH, command=lambda: webbrowser.open(FACEBOOK_URL)); self.b_fb.pack(side="left", padx=3)
        tk.Frame(btns).pack(side="left", fill="x", expand=True)
        self.b_remove = tk.Button(btns, text=self.T("remove"), width=_BW, height=_BH, command=self.remove_selected); self.b_remove.pack(side="left", padx=3)
        self.b_clear = tk.Button(btns, text=self.T("clear"), width=_BW, height=_BH, command=self.clear_list); self.b_clear.pack(side="left", padx=3)
        # 选项行: 4 列 grid 对齐
        # 上行: [语言][方案][帧率][保存] (方案/帧率/保存整体右移一列, 空位给语言)
        # 下行: [稳定参考][局部Warp][平滑强度][输出尺寸]
        opt = tk.Frame(self.root); opt.pack(fill="x", padx=10, pady=8)
        for _c in range(4): opt.grid_columnconfigure(_c, weight=1, uniform="optcol")
        def _cell(row, col):
            f = tk.Frame(opt); f.grid(row=row, column=col, sticky="ew", padx=2, pady=2); return f
        _cL = _cell(0, 0); self.lbl_lang = tk.Label(_cL, text=self.T("lang")); self.lbl_lang.pack(side="left")
        ttk.Combobox(_cL, textvariable=self.lang_name, values=list(LANGS.keys()), width=12, state="readonly").pack(side="right", padx=5)
        _c0 = _cell(0, 1); self.lbl_method = tk.Label(_c0, text=self.T("method")); self.lbl_method.pack(side="left")
        self.method_var = tk.StringVar(value="ffmpeg")
        ttk.Combobox(_c0, textvariable=self.method_var, values=["ffmpeg", "opencv"], width=12, state="readonly").pack(side="right", padx=5)
        _c1 = _cell(0, 2); self.lbl_fps = tk.Label(_c1, text=self.T("fps")); self.lbl_fps.pack(side="left")
        self.fps_var = tk.StringVar(value="24fps")
        ttk.Combobox(_c1, textvariable=self.fps_var, values=FPS_OPTIONS, width=12, state="readonly").pack(side="right")
        _c2 = _cell(0, 3); self.lbl_save_mode = tk.Label(_c2, text=self.T("save_mode")); self.lbl_save_mode.pack(side="left")
        self.save_var = tk.StringVar(value="mp4")
        ttk.Combobox(_c2, textvariable=self.save_var, values=["frames", "mp4"], width=12, state="readonly").pack(side="right")
        _c3 = _cell(1, 0); self.lbl_ref = tk.Label(_c3, text=self.T("ref")); self.lbl_ref.pack(side="left")
        self.ref_var = tk.StringVar(value="global")
        ttk.Combobox(_c3, textvariable=self.ref_var, values=["global", "foreground", "background"], width=12, state="readonly").pack(side="right", padx=5)
        _c4 = _cell(1, 1); self.lbl_warp = tk.Label(_c4, text=self.T("warp")); self.lbl_warp.pack(side="left")
        self.warp_var = tk.StringVar(value="off")
        ttk.Combobox(_c4, textvariable=self.warp_var, values=["off", "mesh_light", "mesh_medium", "mesh_heavy"], width=12, state="readonly").pack(side="right", padx=5)
        _c6 = _cell(1, 2); self.lbl_output_size = tk.Label(_c6, text=self.T("output_size")); self.lbl_output_size.pack(side="left")
        self.output_size_var = tk.StringVar(value="original")
        self.output_size_combo = ttk.Combobox(_c6, textvariable=self.output_size_var, values=["cropped", "original"], width=12, state="readonly"); self.output_size_combo.pack(side="right")
        _c5 = _cell(1, 3); self.lbl_smoothing = tk.Label(_c5, text=self.T("smoothing")); self.lbl_smoothing.pack(side="left")
        self.smooth_var = tk.IntVar(value=30)
        ttk.Spinbox(_c5, from_=5, to=100, textvariable=self.smooth_var, width=12).pack(side="right")
        # 列表
        self.lbl_list = tk.Label(self.root, text=self.T("list")); self.lbl_list.pack(anchor="w", padx=10)
        self.listbox = tk.Listbox(self.root, height=16, selectmode="extended"); self.listbox.pack(fill="both", expand=True, padx=10, pady=5)
        # 下排 (原上排互换下来): 左 [文件][文件夹]  右 [开始][暂停][取消]
        bottom = tk.Frame(self.root); bottom.pack(fill="x", padx=10, pady=(0,4))
        self.b_file = tk.Button(bottom, text=self.T("file"), width=_BW, height=_BH, command=self.add_files); self.b_file.pack(side="left", padx=3)
        self.b_folder = tk.Button(bottom, text=self.T("folder"), width=_BW, height=_BH, command=self.add_folder); self.b_folder.pack(side="left", padx=3)
        # 右侧组: 先 pack 取消(最右), 再暂停, 再开始 -> 视觉上是 开始 暂停 取消, 靠右
        self.b_cancel = tk.Button(bottom, text=self.T("cancel"), width=_BW, height=_BH, command=self.do_cancel); self.b_cancel.pack(side="right", padx=3)
        self.b_pause = tk.Button(bottom, text=self.T("pause"), width=_BW, height=_BH, command=self.toggle_pause); self.b_pause.pack(side="right", padx=3)
        self.b_start = tk.Button(bottom, text=self.T("start"), width=_BW, height=_BH, command=self.start, bg="#4CAF50", fg="white"); self.b_start.pack(side="right", padx=3)
        # 状态: 进度条紧邻左侧显示 Running.... / Done + 保存地址, 可点击打开文件夹, 悬停显示完整提示
        status_frame = tk.Frame(self.root); status_frame.pack(fill="x", padx=10, pady=(0, 0))  # 上面间距减少, 紧贴上面一行
        self.status = tk.Label(status_frame, text=self.T("status")+": -", anchor="w", fg="blue", cursor="hand2", justify="left")
        self.status.pack(side="left", fill="x", expand=True)
        self.status.bind("<Button-1>", lambda e: self.open_last_output())
        self.status.bind("<Enter>", lambda e: self.show_tooltip())
        self.status.bind("<Leave>", lambda e: self.hide_tooltip())
        _pb_frame = tk.Frame(self.root); _pb_frame.pack(fill="x", padx=10, pady=(0, 15))  # 下面离边框 15
        self.pb = ttk.Progressbar(_pb_frame, maximum=100); self.pb.pack(side="left", fill="x", expand=True)
        self.lbl_progress = tk.Label(_pb_frame, text="0%", width=5, anchor="e"); self.lbl_progress.pack(side="right", padx=(5, 0))
        self.last_output_path = None
        self.tooltip = None
        self.refresh_texts()

    def refresh_texts(self):
        self.root.title(self.T("title"))
        for w, k in [(self.b_file,"file"),(self.b_folder,"folder"),(self.b_start,"start"),(self.b_pause,"pause"),(self.b_cancel,"cancel"),(self.b_about,"about"),(self.b_fb,"facebook"),(self.b_clear,"clear"),(self.b_remove,"remove")]:
            w.config(text=self.T(k))
        # 之前只显示中文的标签, 现在全部跟随语言切换
        try: self.lbl_output_size.config(text=self.T("output_size"))
        except Exception: pass
        try:
            self.lbl_ref.config(text=self.T("ref")); self.lbl_warp.config(text=self.T("warp"))
        except Exception: pass
        for w, k in [(self.lbl_lang,"lang"),(self.lbl_method,"method"),(self.lbl_fps,"fps"),(self.lbl_save_mode,"save_mode"),(self.lbl_smoothing,"smoothing"),(self.lbl_list,"list")]:
            try: w.config(text=self.T(k))
            except Exception: pass
        # 保持当前状态文本不被清空, 只在未开始时显示 -
        if not self.running and not getattr(self, 'last_output_path', None):
            self.status.config(text=self.T("status")+": -")

    # ---- 添加 ----
    def add_files(self):
        files = filedialog.askopenfilenames(title=self.T("file"), filetypes=[
            ("All supported", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.wmv *.flv *.mpg *.mpeg *.m2ts *.ts *.3gp *.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp *.gif *.heic *.heif *.avif"),
            ("Video", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.wmv *.flv *.mpg *.mpeg *.m2ts *.ts *.3gp *.asf *.vob *.ogv *.mxf"),
            ("Images", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff *.webp *.gif *.heic *.heif *.avif *.jxl"),
            ("All", "*.*")])
        self._add_paths([Path(f) for f in files])
    def add_folder(self):
        d = filedialog.askdirectory(title=self.T("folder"))
        if not d: return
        folder = Path(d)
        videos = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS]
        frames = list_frames(folder)
        # 如果文件夹里有帧序列, 按帧序列处理 (优先), 否则按视频处理
        if frames and len(frames) >= 2:
            if self.frames_folder is not None and self.frames_folder != folder:
                messagebox.showwarning("Warning", self.T("mixed_frames")); return
            # 如果列表里已有其他帧序列文件夹, 也阻止
            self.frames_folder = folder
            self.tasks.append({"type":"frames","path":folder}); self.listbox.insert("end", f"[Frames {len(frames)}] {folder}")
            self.set_status(self.T("add_frames"))
        elif videos:
            for v in sorted(videos):
                self.tasks.append({"type":"video","path":v}); self.listbox.insert("end", f"[Video] {v}")
            self.set_status(self.T("add_video"))
        else:
            # 递归找子文件夹? 只提示
            messagebox.showinfo("Info", f"No video / frames found in:\n{folder}")

    def on_drop(self, event):
        # tkinterdnd2 传回的是 Tcl 列表, 用 splitlist 解析才能正确处理带空格/中文的路径
        try:
            raw = self.root.tk.splitlist(event.data)
        except Exception:
            import re as _re
            raw = [a or b for a, b in _re.findall(r"\{([^}]+)\}|(\S+)", event.data)]
        debug_log(f"DROP: {raw}")
        self._add_paths([Path(str(x)) for x in raw])
    def _add_path_as_folder(self, folder):
        frames = list_frames(folder)
        if frames and len(frames)>=2:
            if self.frames_folder is not None and self.frames_folder != folder:
                messagebox.showwarning("Warning", self.T("mixed_frames")); return
            self.frames_folder = folder
            self.tasks.append({"type":"frames","path":folder}); self.listbox.insert("end", f"[Frames {len(frames)}] {folder}")
        else:
            for v in sorted([p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO_EXTS]):
                self.tasks.append({"type":"video","path":v}); self.listbox.insert("end", f"[Video] {v}")

    def setup_drag_drop(self):
        # 关键修复: 必须用 TkinterDnD.Tk 创建的窗口 + 在 Listbox 上注册, 普通 tk.Tk 拖拽永远进不来
        try:
            from tkinterdnd2 import DND_FILES
            # 注册到整个窗口和列表, 拖到哪里都能进
            for w in (self.root, self.listbox):
                try:
                    w.drop_target_register(DND_FILES)
                    w.dnd_bind("<<Drop>>", self.on_drop)
                except Exception as e:
                    print("dnd register failed", w, e)
            self._dnd_ok = True
        except Exception:
            debug_log("Drag&Drop NOT available: tkinterdnd2 missing", "warning")
            self._dnd_ok = False
            # 不装 tkinterdnd2 就拖不进, 直接在状态栏提示, 不要静默失败
            try:
                self.set_status("Drag & Drop needs: pip install tkinterdnd2  |  拖拽需要先安装: pip install tkinterdnd2")
            except Exception: pass
    def _add_paths(self, paths):
        # 统一入口: 按钮 / 拖拽 / 文件夹都走这里, 支持视频 + 图片 + 文件夹
        from collections import defaultdict
        img_by_folder = defaultdict(list)
        for p in paths:
            p = Path(p)
            if not p.exists(): continue
            if p.is_dir():
                self._add_path_as_folder(p)
            elif p.suffix.lower() in VIDEO_EXTS:
                self.tasks.append({"type":"video","path":p}); self.listbox.insert("end", f"[Video] {p}")
            elif p.suffix.lower() in IMAGE_EXTS:
                img_by_folder[p.parent].append(p)
            else:
                # 未知后缀: 试着按视频处理, ffmpeg 会报错提示
                self.tasks.append({"type":"video","path":p}); self.listbox.insert("end", f"[Video] {p}")
        # 拖入的图片按文件夹分组, 同一文件夹 = 一个帧序列任务 (遵守不同文件夹不能混放规则)
        for folder, imgs in img_by_folder.items():
            if len(imgs) >= 1:
                if self.frames_folder is not None and self.frames_folder != folder:
                    messagebox.showwarning("Warning", self.T("mixed_frames")); continue
                self.frames_folder = folder
                self.tasks.append({"type":"frames","path":folder}); self.listbox.insert("end", f"[Frames {len(list_frames(folder))}] {folder}")
        if paths:
            self.set_status(self.T("add_video"))
    def clear_list(self):
        if messagebox.askyesno("Confirm", self.T("confirm_clear")):
            self.tasks.clear(); self.listbox.delete(0,"end"); self.frames_folder=None
    def remove_selected(self):
        for i in reversed(self.listbox.curselection()):
            t = self.tasks.pop(i); self.listbox.delete(i)
            if t["type"]=="frames": self.frames_folder=None
    def set_status(self, s):
        # 运行时: 状态改成“运行中...”, 不再显示“状态:”
        if getattr(self, "running", False):
            self._set_status_text(f"{self.T('running')} {s}" if s and s != self.T('running') else self.T('running'))
        else:
            self._set_status_text(f"{self.T('status')}: {s}")
    def _set_status_text(self, text):
        self._status_full = text; self._scroll_pos = 0; self._scroll_dir = 1
        self.status.config(text=text)
    def _tick_scroll(self):
        # 状态文字左右来回移动 (乒乓, 不是单向循环):
        # 长文字: 窗口左右滑动; 短的“运行中...”: 整行左右平移
        try:
            full = self._status_full or ""
            window = 72
            if self.running and len(full) <= window:
                # 短的运行中: 前面空格数 0 -> 25 -> 0 来回, 看起来左右移动
                max_indent = 25
                self._scroll_pos += self._scroll_dir * 2
                if self._scroll_pos >= max_indent: self._scroll_pos = max_indent; self._scroll_dir = -1
                if self._scroll_pos <= 0: self._scroll_pos = 0; self._scroll_dir = 1
                self.status.config(text=" " * self._scroll_pos + full)
            elif len(full) > window:
                padded = full + "        "
                max_pos = len(padded) - window
                self._scroll_pos += self._scroll_dir * 2
                if self._scroll_pos >= max_pos: self._scroll_pos = max_pos; self._scroll_dir = -1
                if self._scroll_pos <= 0: self._scroll_pos = 0; self._scroll_dir = 1
                self.status.config(text=padded[self._scroll_pos:self._scroll_pos+window])
            else:
                self.status.config(text=full)
        except Exception: pass
        self.root.after(300, self._tick_scroll)
    def set_status_output(self, path):
        # Done + 保存地址, 保存路径供点击打开
        import os as _os
        p = str(path)
        self.last_output_path = p
        folder = p if _os.path.isdir(p) else str(Path(p).parent)
        self.last_output_path_folder = folder
        self._set_status_text(f"{self.T('status')}: {self.T('done_prefix')} - {p}  [{self.T('click_hint')}]")
    def open_last_output(self):
        import subprocess as _sp, os as _os
        folder = getattr(self, 'last_output_path_folder', None)
        if folder and _os.path.exists(folder):
            _sp.Popen(f'explorer "{folder}"')
    def show_tooltip(self):
        if not getattr(self, 'last_output_path', None) or self.tooltip: return
        try:
            x = self.root.winfo_pointerx()+12; y = self.root.winfo_pointery()+12
            self.tooltip = tk.Toplevel(self.root); self.tooltip.wm_overrideredirect(True)
            self.tooltip.wm_geometry(f"+{x}+{y}")
            lbl = tk.Label(self.tooltip, text=f"{self.T('done_prefix')}\n{self.last_output_path}\n{self.T('click_hint')}", bg="#ffffe0", relief="solid", borderwidth=1, justify="left")
            lbl.pack()
        except Exception: pass
    def hide_tooltip(self):
        if self.tooltip:
            try: self.tooltip.destroy()
            except Exception: pass
            self.tooltip = None
    def toggle_pause(self):
        self.paused = not self.paused
        self.set_status(self.T("paused") if self.paused else "Running...")
    def do_cancel(self):
        self.cancelled = True; self.paused=False; self.set_status(self.T("cancelled"))
    def show_about(self): messagebox.showinfo(self.T("about"), self.T("about_text"))
    def poll_queue(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind=="progress": self.pb["value"]=val; self.lbl_progress.config(text=f"{int(val)}%")
                elif kind=="status": self.set_status(val)
                elif kind=="output": self.set_status_output(val)
                elif kind=="done": self.running=False; self.pb["value"]=100; self.lbl_progress.config(text="100%")
                # done 时若已有 output, 保留 Done+地址, 不覆盖
        except queue.Empty: pass
        self.root.after(200, self.poll_queue)

    def start(self):
        debug_log(f"GUI start clicked: output_size={self.output_size_var.get()} tasks={len(self.tasks)} method={self.method_var.get()} smoothing={self.smooth_var.get()} fps={self.fps_var.get()} save={self.save_var.get()} lang={self.lang_name.get()}")
        if self.running: return
        if not self.tasks:
            messagebox.showwarning("Warning", self.T("no_task")); return
        self.cancelled=False; self.paused=False; self.running=True; self.pb["value"]=0; self.lbl_progress.config(text="0%"); self.set_status(self.T("running"))
        threading.Thread(target=self.worker, daemon=True).start()

    def worker(self):
        method = self.method_var.get(); smoothing = int(self.smooth_var.get()); keep_original = (self.output_size_var.get() == 'original'); ref = self.ref_var.get(); warp = self.warp_var.get()
        fps_label = self.fps_var.get(); save_mode = self.save_var.get()
        total = len(self.tasks)
        def prog(cur, tot): self.q.put(("progress", cur/tot*100))
        for idx, task in enumerate(list(self.tasks)):
            if self.cancelled: break
            while self.paused and not self.cancelled: time.sleep(0.3)
            if self.cancelled: break
            try:
                if task["type"]=="video":
                    self.q.put(("status", f"[{idx+1}/{total}] {task['path'].name}"))
                    out = stabilize_video_file(task["path"], method=method, smoothing=smoothing, keep_original_size=keep_original, ref=ref, warp=warp, on_progress=prog)
                    self.q.put(("output", str(out)))
                    self.q.put(("status", f"Done -> {Path(out).name}"))
                else:
                    folder = task["path"]
                    self.q.put(("status", f"[{idx+1}/{total}] Frames: {folder.name}"))
                    def prog(cur, tot): self.q.put(("progress", cur/tot*100))
                    if method=="ffmpeg":
                        if save_mode=="frames":
                            out_dir = output_frames_dir(folder)
                            stabilize_frames_ffmpeg_x_only(folder, out_dir, smoothing=smoothing, fps_label=fps_label, save_as="frames", keep_original_size=keep_original)
                        else:
                            stabilize_frames_ffmpeg_x_only(folder, folder, smoothing=smoothing, fps_label=fps_label, save_as="mp4", keep_original_size=keep_original)
                    else:
                        if save_mode=="frames":
                            out_dir = output_frames_dir(folder)
                            stabilize_frames_opencv_x_only(folder, out_dir, smoothing_radius=smoothing, on_progress=prog, keep_original_size=keep_original, ref=ref, warp=warp)
                        else:
                            # OpenCV -> 帧 -> 再用 ffmpeg 合成 mp4
                            tmp_stable = folder.parent / f"__stable_tmp_{folder.name}"
                            import shutil
                            if tmp_stable.exists(): shutil.rmtree(tmp_stable)
                            stabilize_frames_opencv_x_only(folder, tmp_stable, smoothing_radius=smoothing, on_progress=prog, keep_original_size=keep_original, ref=ref, warp=warp)
                            # 先把稳定帧重命名为 frame_%04d.jpg 顺序名 (Gyan 版不支持 glob, 稳定帧原名是 *_opencv_stablized.jpg)
                            _ss0 = sorted(tmp_stable.glob("*.jpg"))
                            for _idx, _sf in enumerate(_ss0, start=1):
                                _tg = tmp_stable / f"frame_{_idx:04d}.jpg"
                                if _sf.resolve() != _tg.resolve():
                                    if _tg.exists(): _tg.unlink()
                                    _sf.rename(_tg)
                            # 合成 mp4, 命名: 文件夹名_fps_stablized.mp4, 尺寸由稳定后帧决定 (已裁左右)
                            import cv2
                            first = cv2.imread(str(sorted(tmp_stable.glob('*.jpg'))[0])); h,w = first.shape[:2]
                            from vid_stablizer import FFMPEG, parse_fps_label
                            import subprocess
                            mp4 = folder.parent / f"{folder.name}_{fps_label}_opencv_stablized.mp4"
                            subprocess.run([FFMPEG,"-y","-framerate",parse_fps_label(fps_label),"-i",str(tmp_stable/"frame_%04d.jpg"),"-c:v","libx265","-crf","18","-preset","medium","-tag:v","hvc1",str(mp4)], check=False, **_NO_WINDOW)
                            # 注意: OpenCV 输出文件名是 原名_stablized.jpg, 不是 frame_%04d, 这里用 glob 方式合成
                            # Gyan 版不支持 glob: 先把稳定帧重命名为 frame_%04d.jpg 再用顺序名重试
                            if not mp4.exists():
                                _ss = sorted(tmp_stable.glob("*.jpg"))
                                for _idx, _sf in enumerate(_ss, start=1):
                                    _tg = tmp_stable / f"frame_{_idx:04d}.jpg"
                                    if _sf.resolve() != _tg.resolve():
                                        if _tg.exists(): _tg.unlink()
                                        _sf.rename(_tg)
                                subprocess.run([FFMPEG,"-y","-framerate",parse_fps_label(fps_label),"-i",str(tmp_stable/"frame_%04d.jpg"),"-c:v","libx265","-crf","18","-preset","medium","-tag:v","hvc1",str(mp4)], check=False, **_NO_WINDOW)
                            shutil.rmtree(tmp_stable, ignore_errors=True)
                    _out = str(output_frames_dir(folder)) if save_mode=="frames" else str(folder.parent / f"{folder.name}_{fps_label}_{method}_stablized.mp4")
                    self.q.put(("output", _out))
                    self.q.put(("status", f"Done -> {folder.name}"))
            except Exception as e:
                debug_log(f"ERROR task {task['path']}: {e}", "error")
                import traceback; debug_log(traceback.format_exc(), "error")
                self.q.put(("status", f"Error {task['path'].name}: {e}"))
            self.q.put(("progress", (idx+1)/total*100))
        self.q.put(("done", None))

if __name__ == "__main__":
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
    except Exception:
        print("tkinterdnd2 not installed, drag & drop disabled. Run: pip install tkinterdnd2")
        root = tk.Tk()
    App(root); root.mainloop()
