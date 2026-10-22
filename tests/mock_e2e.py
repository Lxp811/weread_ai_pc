#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线自测：用本地 mock 的 DeepSeek 服务验证整条答题链路。

不访问外网。运行：python tests/mock_e2e.py
"""

import json
import os
import socket
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")

import weread_helper as wh  # noqa: E402

CALLS = []
MODE = {"search_empty": False, "auth": 200, "bad_index": False, "truncate": False}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # 静音
        pass

    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        CALLS.append((self.path, self.headers.get("x-api-key"),
                      self.headers.get("Authorization"), payload))

        if MODE["auth"] != 200:
            return self._send(MODE["auth"], {"error": {"message": "bad key"}})

        if self.path == "/v1/tools/search":
            query = payload["query"]
            assert 1 <= len(query) <= 128, f"query 长度越界: {len(query)}"
            assert payload["count"] in range(3, 9)
            if MODE["search_empty"]:
                return self._send(200, {"results": []})
            return self._send(200, {"results": [
                {"title": "中国首都 - 百科", "url": "https://example.com/a",
                 "summary": "北京是中华人民共和国的首都。"},
                {"title": "首都资料", "url": "https://example.com/b",
                 "summary": "北京为政治文化中心。"},
            ]})

        if self.path == "/anthropic/v1/messages":
            content = payload["messages"][0]["content"]
            if isinstance(content, list):
                kinds = [c.get("type") for c in content]
                assert kinds == ["text", "image"], kinds
                assert content[1]["source"]["type"] == "base64"
                assert content[1]["source"]["media_type"] == "image/jpeg"
                raw = BytesIO(__import__("base64").b64decode(
                    content[1]["source"]["data"]))
                from PIL import Image
                img = Image.open(raw)
                assert img.format == "JPEG" and max(img.size) <= 1600, img.size
                text = ("QUESTION: 微信读书的「每日一答」每天可以答几轮？\n"
                        "OPTION1: 一轮\nOPTION2: 两轮\nOPTION3: 三轮")
                return self._send(200, {"content": [{"type": "text", "text": text}]})
            idx = 4 if MODE["bad_index"] else 2
            if MODE["truncate"] and payload.get("max_tokens", 0) < 1800:
                return self._send(200, {
                    "stop_reason": "max_tokens",
                    "content": [{"type": "thinking", "thinking": "思考中，被截断"}]})
            return self._send(200, {"content": [
                {"type": "text", "text": f"COUNT=3\nANSWER={idx}"}]})

        return self._send(404, {"error": {"message": "not found"}})


def start_server():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def make_image(size=(900, 700)):
    from PIL import Image, ImageDraw
    img = Image.new("RGB", size, (8, 30, 60))
    d = ImageDraw.Draw(img)
    d.text((40, 60), "微信读书 每日一答", fill=(255, 255, 255))
    d.text((40, 200), "A. 一轮", fill=(220, 235, 255))
    d.text((40, 300), "B. 两轮", fill=(220, 235, 255))
    return img


def check(name, fn):
    try:
        fn()
        print(f"  PASS  {name}")
        return True
    except Exception as exc:
        print(f"  FAIL  {name}: {exc}")
        traceback.print_exc()
        return False


def main():
    import shutil
    tmp = Path(__file__).resolve().parent / "_tmp_config"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    wh.APP_DIR = tmp
    wh.CONFIG_PATH = tmp / "config.json"
    wh.LOG_PATH = tmp / "helper.log"
    global CALLS
    srv, port = start_server()
    global BASE
    base = f"http://127.0.0.1:{port}"
    BASE = base
    print(f"mock server: {base}")
    ok = True

    def cfg(**kw):
        defaults = dict(endpoint=base, model="deepseek-flash", search_count=5,
                        temperature=0.2, api_key="sk-test")
        defaults.update(kw)
        return wh.Config(**defaults)

    def t_roundtrip():
        CALLS.clear()
        jpeg = wh.encode_jpeg(make_image(), max_edge=800)
        ans = wh.solve(jpeg, cfg())
        assert (ans.index, ans.count) == (2, 3), (ans.index, ans.count)
        assert ans.option == "两轮", ans.option
        assert len(CALLS) == 3, [c[0] for c in CALLS]
        paths = [c[0] for c in CALLS]
        assert paths == ["/anthropic/v1/messages", "/v1/tools/search",
                         "/anthropic/v1/messages"], paths
        assert CALLS[1][2] == "Bearer sk-test", CALLS[1][2]
        assert CALLS[0][1] == "sk-test", CALLS[0][1]
        assert CALLS[0][3]["model"] == "deepseek-flash"

    def t_jpeg_limits():
        big = wh.encode_jpeg(make_image((4000, 3000)))
        from PIL import Image
        img = Image.open(BytesIO(big))
        assert max(img.size) == 1600, img.size
        small = wh.encode_jpeg(make_image((320, 200)))
        assert Image.open(BytesIO(small)).size == (320, 200)

    def t_search_query():
        q = wh.Question(
            text="《红楼梦》的作者是[填空]，他是清代作家，生活在十八世纪中期",
            options=["曹雪芹", "罗贯中", "施耐庵", "吴承恩"],
        )
        query = q.search_query()
        assert 1 <= len(query) <= 128, len(query)
        assert "曹雪芹" in query, query
        assert "[填空]" not in query

    def t_auth_error():
        MODE["auth"] = 401
        try:
            wh.solve(wh.encode_jpeg(make_image()), cfg())
        except wh.ApiError as exc:
            assert "API Key" in str(exc), exc
        else:
            raise AssertionError("401 应该抛错")
        finally:
            MODE["auth"] = 200

    def t_empty_search():
        MODE["search_empty"] = True
        try:
            wh.solve(wh.encode_jpeg(make_image()), cfg())
        except wh.ApiError as exc:
            assert "没搜到" in str(exc), exc
        else:
            raise AssertionError("空搜索结果应该抛错")
        finally:
            MODE["search_empty"] = False

    def t_bad_index():
        MODE["bad_index"] = True
        try:
            wh.solve(wh.encode_jpeg(make_image()), cfg())
        except wh.ApiError as exc:
            assert "超出选项数" in str(exc), exc
        else:
            raise AssertionError("越界序号应该抛错")
        finally:
            MODE["bad_index"] = False

    def t_endpoint_guard():
        for bad in ("http://api.deepseek.com", "ftp://x", "https://api.deepseek.com?a=1"):
            try:
                wh._validate_endpoint(bad)
            except wh.ApiError:
                continue
            raise AssertionError(f"{bad} 应该被拒绝")

    def t_dpapi():
        secret = "sk-abcdef1234567890"
        stored = wh.protect_key(secret)
        assert secret not in stored
        assert wh.unprotect_key(stored) == secret

    def t_truncate():
        CALLS.clear()
        MODE["truncate"] = True
        try:
            ans = wh.solve(wh.encode_jpeg(make_image()), cfg())
            assert ans.index == 2, ans.index
            paths = [c[0] for c in CALLS]
            assert paths.count("/anthropic/v1/messages") == 3, paths
        finally:
            MODE["truncate"] = False

    def t_region():
        import time as _t
        import tkinter as _tk

        root = _tk.Tk()
        root.withdraw()
        app = wh.App(root)
        root.update()
        app.pick_region()
        root.update()
        ov = app._selector
        assert ov.winfo_exists()
        canvas = ov.winfo_children()[0]
        canvas.event_generate("<ButtonPress-1>", x=40, y=60)
        canvas.event_generate("<B1-Motion>", x=440, y=360)
        canvas.event_generate("<ButtonRelease-1>", x=440, y=360)
        deadline = _t.time() + 2
        while _t.time() < deadline and app.cfg.region is None:
            root.update()
            _t.sleep(0.05)
        assert app.cfg.region == [40, 60, 400, 300], app.cfg.region
        assert not ov.winfo_exists(), "框选窗口没有关闭"
        assert root.state() == "normal", root.state()
        root.destroy()

    def t_diag():
        import time as _t
        import tkinter as _tk

        root = _tk.Tk()
        root.withdraw()
        app = wh.App(root)
        root.update()
        app.toggle_settings()
        app.key_entry.delete(0, "end")
        app.key_entry.insert(0, " sk-test ")
        app.endpoint_entry.delete(0, "end")
        app.endpoint_entry.insert(0, BASE)
        app.diagnose()
        content = ""
        deadline = _t.time() + 8
        while _t.time() < deadline:
            root.update()
            _t.sleep(0.05)
            if app.diag_text is not None:
                content = app.diag_text.get("1.0", "end")
                if "检查结束" in content:
                    break
        assert "① 网络连通" in content, content
        assert "② 鉴权与模型" in content, content
        assert "③ 搜索接口：正常" in content, content
        assert "太短" in content, content
        root.destroy()

    def t_grab():
        from PIL import ImageGrab
        img = ImageGrab.grab()
        assert img.width > 100 and img.height > 100, img.size

    def t_ui():
        import tkinter as tk
        wh._enable_dpi_awareness()
        root = tk.Tk()
        root.withdraw()
        app = wh.App(root)
        root.update()
        assert app.answer_label.cget("text") == "？"
        app._set_busy(True)
        assert str(app.primary.cget("state")) == "disabled"
        app._set_busy(False)
        app.answer_label.config(text="第 2 个")
        app.toggle_settings()
        root.update()
        app.toggle_settings()
        root.destroy()

    for name, fn in [
        ("三阶段完整链路", t_roundtrip),
        ("图片缩放与 JPEG 编码", t_jpeg_limits),
        ("填空题搜索 query", t_search_query),
        ("401 提示", t_auth_error),
        ("搜索为空报错", t_empty_search),
        ("答案序号越界", t_bad_index),
        ("根地址校验", t_endpoint_guard),
        ("API Key DPAPI 加密", t_dpapi),
        ("截断自动重试", t_truncate),
        ("诊断报告", t_diag),
        ("框选区域", t_region),
        ("屏幕截取", t_grab),
        ("界面构建", t_ui),
    ]:
        ok = check(name, fn) and ok

    srv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    print("\n全部通过" if ok else "\n有失败项")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
