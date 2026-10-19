#!/usr/bin/env python3
# timetable.py
# 桌面课表小工具：可拖动的常驻窗口，显示当天课程；支持截图 OCR 一键导入、
# 手动添加、文本导入。纯标准库 + Windows 自带 OCR（无需安装 Tesseract）。
# Desktop class-schedule widget: draggable always-on-top window showing today's
# classes; import via screenshot OCR (Windows.Media.Ocr), manual add, or text import.
#
# 用法 / Usage:  py timetable.py
# 依赖 / Deps:   仅标准库 / stdlib only（OCR 用系统 WinRT，仅 Windows 10/11）。

import os
import re
import json
import ctypes
import datetime
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox


def hide_console():
    """隐藏控制台黑窗（仅当有控制台时）/ Hide the console window if any."""
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
    except Exception:
        pass

DATA_DIR = os.path.join(os.environ.get("APPDATA", "."), "ClassSchedule")
DATA_FILE = os.path.join(DATA_DIR, "courses.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
WEEK = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


# ----------------------------- 数据 / Storage -----------------------------

def load_courses():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def save_courses(courses):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(courses, f, ensure_ascii=False, indent=2)


def load_settings():
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(s):
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=2)


def today_courses(courses):
    d = datetime.date.today().isoweekday()  # 1=Mon .. 7=Sun
    today = [c for c in courses if c.get("day") == d]
    today.sort(key=lambda c: c.get("start", ""))
    return d, today


# ----------------------------- OCR / 截图识别 -----------------------------

OCR_PS = r'''
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime]
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime]
$path = $args[0]
try {
    $file = [Windows.Storage.StorageFile]::GetFileFromPathAsync($path).GetAwaiter().GetResult()
    $stream = $file.OpenReadAsync().GetAwaiter().GetResult()
    $decoder = [Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream).GetAwaiter().GetResult()
    $bmp = $decoder.GetSoftwareBitmapAsync().GetAwaiter().GetResult()
    $ocr = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if ($null -eq $ocr) { $ocr = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage("zh") }
    $res = $ocr.RecognizeAsync($bmp).GetAwaiter().GetResult()
    [Console]::Out.Write($res.Text)
} catch {
    [Console]::Error.Write("OCR_ERROR: " + $_.Exception.Message)
}
'''


def ocr_image(path):
    """用 Windows 自带 OCR 识别图片文字 / Recognize text via system OCR."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-Command", OCR_PS, path],
                           capture_output=True, timeout=120)
        out = (r.stdout or b"").decode("utf-8", "replace")
        err = (r.stderr or b"").decode("utf-8", "replace")
        if "OCR_ERROR" in err:
            return None, err
        return out, None
    except Exception as e:
        return None, str(e)


# ----------------------------- 文本解析 / Parse -----------------------------

WD_NAMES = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def parse_timetable_text(text):
    """尽力把课表文字解析成课程 / Best-effort parse timetable text -> courses."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    courses = []
    cur_day = 1
    time_re = re.compile(r"(\d{1,2}[:：]\d{2})\s*[-~–]\s*(\d{1,2}[:：]\d{2})")
    for line in lines:
        for i, name in enumerate(WD_NAMES):
            if name in line or ("星期" + "一二三四五六日"[i]) in line:
                cur_day = i + 1
        m = time_re.search(line)
        # 课程名：含 4 个以上中文字符 / a token with >=4 CJK chars
        cjk = re.findall(r"[\u4e00-\u9fff]{4,}", line)
        loc = re.findall(r"(?:教|室|楼|栋|馆|区)\S{0,8}", line)
        if m and cjk:
            courses.append({
                "day": cur_day,
                "start": m.group(1).replace("：", ":"),
                "end": m.group(2).replace("：", ":"),
                "name": cjk[0],
                "loc": loc[0] if loc else "",
                "teacher": "",
                "weeks": "",
            })
    return courses


# ----------------------------- 小部件窗口 / Widget -----------------------------

class Widget(tk.Toplevel):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.title("课表 / Timetable")
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.92)
        self.configure(bg="#1e1f22", bd=1, relief="solid")
        self._dx = self._dy = 0

        # 拖动条 / drag handle
        bar = tk.Frame(self, bg="#2b2d30", height=22)
        bar.pack(fill="x")
        tk.Label(bar, text="📅 今日课表 / Today", bg="#2b2d30",
                 fg="#e6e6e6", font=("", 9, "bold")).pack(side="left", padx=8)
        tk.Button(bar, text="⚙", bg="#2b2d30", fg="#e6e6e6", bd=0,
                  command=self.app.open_manage).pack(side="right", padx=2)
        tk.Button(bar, text="×", bg="#2b2d30", fg="#ef5350", bd=0,
                  command=self.app.quit_all).pack(side="right", padx=2)
        tk.Label(bar, text="", bg="#2b2d30").pack(side="right", padx=2)

        self.body = tk.Frame(self, bg="#1e1f22")
        self.body.pack(fill="both", padx=10, pady=6)
        self.refresh()

        # 拖动绑定到整个窗口（标题文字 Label 会吃掉事件，故绑顶层）/ bind drag on whole window
        self.bind("<Button-1>", self.start_move)
        self.bind("<B1-Motion>", self.on_move)
        self.bind("<ButtonRelease-1>", self.end_move)
        self._dragging = False

        # 初始位置：记住上次位置，否则放右上角 / restore last pos, else top-right
        self.update_idletasks()
        s = load_settings()
        if "pos" in s and isinstance(s["pos"], list):
            x, y = s["pos"][:2]
        else:
            x = max(0, self.winfo_screenwidth() - self.winfo_width() - 20)
            y = 20
        self.geometry(f"+{int(x)}+{int(y)}")

    def start_move(self, e):
        self._dx, self._dy = e.x_root, e.y_root
        self._dragging = True

    def on_move(self, e):
        if not self._dragging:
            return
        x = self.winfo_x() + e.x_root - self._dx
        y = self.winfo_y() + e.y_root - self._dy
        self.geometry(f"+{x}+{y}")
        self._dx, self._dy = e.x_root, e.y_root

    def end_move(self, e):
        self._dragging = False
        save_settings({"pos": [self.winfo_x(), self.winfo_y()]})

    def refresh(self):
        for w in self.body.winfo_children():
            w.destroy()
        d, today = today_courses(self.app.courses)
        head = tk.Label(self.body,
                        text=f"{datetime.date.today():%Y-%m-%d} {WEEK[d-1]}",
                        bg="#1e1f22", fg="#e6a23c", font=("", 11, "bold"))
        head.pack(anchor="w", pady=(0, 4))
        if not today:
            tk.Label(self.body, text="  今天没课 🎉 / No classes",
                     bg="#1e1f22", fg="#9e9e9e").pack(anchor="w")
        for c in today:
            line = f"{c['start']}-{c['end']}  {c['name']}"
            if c.get("loc"):
                line += f"  @{c['loc']}"
            tk.Label(self.body, text=line, bg="#1e1f22", fg="#e6e6e6",
                     font=("", 10)).pack(anchor="w")
        self.update_idletasks()


# ----------------------------- 管理窗口 / Manage -----------------------------

class Manage(tk.Toplevel):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.title("课表管理 / Manage Timetable")
        self.configure(bg="#1e1f22")
        self.geometry("620x520")

        # 课程列表 / list
        cols = ("day", "start", "end", "name", "loc", "teacher")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12)
        headers = ["星期", "开始", "结束", "课程", "地点", "教师"]
        for c, h in zip(cols, headers):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=70 if c in ("day",) else 90)
        for c in app.courses:
            self.tree.insert("", "end", values=(
                WEEK[c.get("day", 1) - 1], c.get("start", ""), c.get("end", ""),
                c.get("name", ""), c.get("loc", ""), c.get("teacher", "")))
        self.tree.pack(fill="both", expand=True, padx=10, pady=8)

        btns = tk.Frame(self, bg="#1e1f22")
        btns.pack(fill="x", padx=10, pady=4)
        for txt, cmd in [("添加 / Add", self.add_course),
                         ("编辑 / Edit", self.edit_course),
                         ("删除 / Del", self.del_course),
                         ("导入截图(OCR)", self.import_ocr),
                         ("文本导入", self.import_text),
                         ("保存 / Save", self.do_save)]:
            tk.Button(btns, text=txt, bg="#2b2d30", fg="#e6e6e6", bd=0,
                      command=cmd).pack(side="left", padx=3, pady=2)

        tk.Button(btns, text="刷新窗口 / Refresh", bg="#e6a23c", fg="#1e1f22",
                  bd=0, command=lambda: self.app.widget.refresh()).pack(
                      side="right", padx=3, pady=2)
        self.pack_buttons = btns

    def _reload(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for c in self.app.courses:
            self.tree.insert("", "end", values=(
                WEEK[c.get("day", 1) - 1], c.get("start", ""), c.get("end", ""),
                c.get("name", ""), c.get("loc", ""), c.get("teacher", "")))

    def add_course(self):
        self.edit_form(None)

    def edit_course(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "先选中一行 / select a row first")
            return
        idx = self.tree.index(sel[0])
        self.edit_form(self.app.courses[idx])

    def del_course(self):
        sel = self.tree.selection()
        if not sel:
            return
        idx = self.tree.index(sel[0])
        del self.app.courses[idx]
        self._reload()

    def edit_form(self, course):
        f = tk.Toplevel(self)
        f.title("课程 / Course")
        f.configure(bg="#1e1f22")
        cur = course or {}
        vars_ = {k: tk.StringVar(value=str(cur.get(k, ""))) for k in
                 ("start", "end", "name", "loc", "teacher", "weeks")}
        day_var = tk.StringVar(value=WEEK[(cur.get("day", 1) - 1)])

        tk.Label(f, text="星期 / Day", bg="#1e1f22", fg="#e6e6e6").grid(
            row=0, column=0, padx=6, pady=4, sticky="e")
        ttk.Combobox(f, textvariable=day_var, values=WEEK,
                     width=12, state="readonly").grid(row=0, column=1, padx=6)
        labels = [("开始 / Start", "start"), ("结束 / End", "end"),
                  ("课程 / Name", "name"), ("地点 / Loc", "loc"),
                  ("教师 / Teacher", "teacher"), ("周次 / Weeks", "weeks")]
        for i, (lab, key) in enumerate(labels, start=1):
            tk.Label(f, text=lab, bg="#1e1f22", fg="#e6e6e6").grid(
                row=i, column=0, padx=6, pady=4, sticky="e")
            tk.Entry(f, textvariable=vars_[key], bg="#2b2d30",
                     fg="#e6e6e6", insertbackground="#e6e6e6").grid(
                         row=i, column=1, padx=6)

        def commit():
            rec = {k: vars_[k].get().strip() for k in vars_}
            rec["day"] = WEEK.index(day_var.get()) + 1
            if not rec["name"]:
                messagebox.showwarning("提示", "课程名不能为空 / name required")
                return
            if course:
                idx = self.app.courses.index(course)
                self.app.courses[idx] = rec
            else:
                self.app.courses.append(rec)
            self._reload()
            f.destroy()

        tk.Button(f, text="确定 / OK", bg="#e6a23c", fg="#1e1f22",
                  command=commit).grid(row=7, column=0, columnspan=2, pady=8)

    def do_save(self):
        save_courses(self.app.courses)
        self.app.widget.refresh()
        messagebox.showinfo("已保存", "已保存到\n" + DATA_FILE)

    def import_text(self):
        t = tk.Toplevel(self)
        t.title("文本导入 / Text import")
        t.configure(bg="#1e1f22")
        t.geometry("500x460")
        st = scrolledtext.ScrolledText(t, bg="#141517", fg="#e6e6e6",
                                      font=("Consolas", 10))
        st.pack(fill="both", expand=True, padx=8, pady=8)
        st.insert("end", "把教务系统导出的课表文字粘贴到这里，每行尽量包含：\n"
                         "星期、时间(如 08:00-09:40)、课程名、地点。\n"
                         "Paste exported timetable text; lines with weekday + time + name.\n")

        def parse():
            parsed = parse_timetable_text(st.get("1.0", "end"))
            if not parsed:
                messagebox.showinfo("结果", "未解析出课程，请手动添加 / no courses parsed")
                return
            for c in parsed:
                self.app.courses.append(c)
            self._reload()
            messagebox.showinfo("结果", f"解析并导入 {len(parsed)} 条，请核对 / imported {len(parsed)}")
            t.destroy()

        tk.Button(t, text="解析并导入 / Parse & import", bg="#e6a23c",
                  fg="#1e1f22", command=parse).pack(pady=6)

    def import_ocr(self):
        path = filedialog.askopenfilename(
            title="选择课表截图 / pick screenshot",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp")])
        if not path:
            return
        text, err = ocr_image(path)
        if text is None:
            messagebox.showerror("OCR 失败", err or "无法识别 / OCR failed")
            return
        # 复用文本导入界面，预填 OCR 结果 / reuse text UI with OCR result
        t = tk.Toplevel(self)
        t.title("OCR 结果 / OCR result")
        t.configure(bg="#1e1f22")
        t.geometry("500x460")
        st = scrolledtext.ScrolledText(t, bg="#141517", fg="#e6e6e6",
                                      font=("Consolas", 10))
        st.pack(fill="both", expand=True, padx=8, pady=8)
        st.insert("end", text + "\n\n— 上方为识别文字，点下面按钮自动解析 —\n"
                                "OCR text above; click below to auto-parse.")

        def parse():
            parsed = parse_timetable_text(text)
            if not parsed:
                messagebox.showinfo("结果", "未解析出课程，可手动添加 / none parsed")
                return
            for c in parsed:
                self.app.courses.append(c)
            self._reload()
            messagebox.showinfo("结果", f"解析并导入 {len(parsed)} 条，请核对 / imported {len(parsed)}")
            t.destroy()

        tk.Button(t, text="解析并导入 / Parse & import", bg="#e6a23c",
                  fg="#1e1f22", command=parse).pack(pady=6)


# ----------------------------- 主程序 / App -----------------------------

class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.courses = load_courses()
        self.widget = Widget(self)
        self.manage = None

    def open_manage(self):
        if self.manage is None or not self.manage.winfo_exists():
            self.manage = Manage(self)
        else:
            self.manage.lift()

    def quit_all(self):
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    hide_console()
    App().run()
