# Timetable

桌面课表小工具：一个**可拖动**的常驻窗口，显示**当天**的课程；支持从教务系统截图**一键 OCR 导入**、手动添加、文本导入。纯 Python 标准库，OCR 用 Windows 10/11 自带的 `Windows.Media.Ocr`，无需安装 Tesseract。

A draggable always-on-top desktop widget showing **today's** classes. Import via screenshot **OCR** (system `Windows.Media.Ocr`, no Tesseract), manual add, or text import. Python stdlib only.

## 功能 / Features

- **可拖动窗口**：无边框、置顶、半透明，拖动顶部条移动；右上 ⚙ 管理、× 退出。
  Draggable borderless always-on-top widget; drag the top bar to move.
- **当天课表**：自动按系统日期显示当天课程（时间 / 课程 / 地点）。
  Auto shows today's classes by system date.
- **截图 OCR 导入**：选课表截图 → 系统 OCR 出文字 → 自动解析成课程，可核对后保存。
  Screenshot OCR: pick image → system OCR → auto-parse into courses.
- **手动添加 / 编辑 / 删除**：表单录入星期、起止时间、课程、地点、教师、周次。
- **文本导入**：粘贴教务系统导出的课表文字，自动解析。
- **数据保存**：存于 `APPDATA\ClassSchedule\courses.json`，下次启动自动加载。
  Stored in `APPDATA\ClassSchedule\courses.json`.

## 用法 / Usage

```powershell
py timetable.py
```

启动后桌面出现课表窗口；点 ⚙ 打开管理窗口：添加课程、导入截图(OCR)、文本导入、保存。「刷新窗口」按钮把改动同步到桌面窗口。

After launch the widget appears on desktop; click ⚙ to manage: add, OCR import, text import, save. "Refresh" syncs changes to the widget.

## 说明 / Notes

- OCR 只能识别文字，**解析出的星期/时间可能需手动核对**（课表版式各不同）。
  OCR reads text; parsed weekday/time may need manual verification (layouts differ).
- 若 OCR 不可用（非 Windows 10/11 或缺少语言包），可用「文本导入」或手动添加。
  If OCR is unavailable, use text import or manual add.
- 课程文件位置 / data file: `%APPDATA%\ClassSchedule\courses.json`

## 依赖 / Dependencies

仅 Python 标准库 / stdlib only. 用 **`py`** 启动器运行 / run with the **`py`** launcher.
