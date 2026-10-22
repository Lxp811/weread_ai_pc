#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开发用：给界面截图，检查布局。不参与日常使用。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tkinter as tk  # noqa: E402

import weread_helper as wh  # noqa: E402


def main() -> None:
    wh._enable_dpi_awareness()
    root = tk.Tk()
    app = wh.App(root)
    root.geometry("+160+120")
    root.update()

    shots = []

    def snap(name):
        root.update_idletasks()
        root.update()
        x, y = root.winfo_rootx(), root.winfo_rooty()
        w, h = root.winfo_width(), root.winfo_height()
        from PIL import ImageGrab
        img = ImageGrab.grab(bbox=(x - 2, y - 2, x + w + 2, y + h + 2))
        path = Path(__file__).resolve().parent.parent / name
        img.save(path)
        shots.append(path)

    def step1():
        snap("preview_idle.png")
        app.answer_label.config(text="第 2 个", fg=wh.OK)
        app.option_label.config(text="两轮\n微信读书的「每日一答」每天可以答几轮？\n一轮 / 两轮 / 三轮", fg=wh.TEXT)
        app.set_status("完成 · 已联网核对 · 用时 7.4s", wh.OK)
        root.update()
        root.after(300, step2)

    def step2():
        snap("preview_answer.png")
        app.toggle_settings()
        root.update()
        root.after(300, step3)

    def step3():
        snap("preview_settings.png")
        root.destroy()

    root.after(600, step1)
    root.mainloop()
    print("saved:", [p.name for p in shots])


if __name__ == "__main__":
    main()
