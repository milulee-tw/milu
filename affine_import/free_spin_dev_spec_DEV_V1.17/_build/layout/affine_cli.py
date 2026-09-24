#!/usr/bin/env python3
"""驅動 affine-mcp-server（stdio）的小客戶端。

用途：把大量 base64 內容留在腳本裡，不經過對話。
用法：
    python3 affine_cli.py upload <檔案路徑> [<檔案路徑> ...]
    python3 affine_cli.py call <工具名> <參數JSON檔>
"""
import base64
import json
import mimetypes
import os
import subprocess
import sys
import threading

CMD = ["npx", "-y", "-p", "affine-mcp-server@3.7.0", "affine-mcp"]


class MCP:
    def __init__(self):
        self.p = subprocess.Popen(
            CMD, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1,
        )
        self._id = 0
        # 把 server 的 stderr 丟掉，避免塞爆 pipe
        threading.Thread(target=self._drain, daemon=True).start()

    def _drain(self):
        for _ in self.p.stderr:
            pass

    def _send(self, method, params=None, notify=False):
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        if not notify:
            self._id += 1
            msg["id"] = self._id
        self.p.stdin.write(json.dumps(msg) + "\n")
        self.p.stdin.flush()
        if notify:
            return None
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("server 沒有回應就結束了")
            line = line.strip()
            if not line:
                continue
            try:
                res = json.loads(line)
            except json.JSONDecodeError:
                continue
            if res.get("id") == self._id:
                if "error" in res:
                    raise RuntimeError(json.dumps(res["error"], ensure_ascii=False))
                return res.get("result")

    def start(self):
        self._send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "milu-uploader", "version": "1.0"},
        })
        self._send("notifications/initialized", {}, notify=True)

    def call(self, name, args):
        res = self._send("tools/call", {"name": name, "arguments": args})
        out = []
        for c in res.get("content", []):
            if c.get("type") == "text":
                out.append(c["text"])
        return "\n".join(out)

    def close(self):
        try:
            self.p.stdin.close()
            self.p.wait(timeout=10)
        except Exception:
            self.p.kill()


def workspace_id():
    ws = os.environ.get("AFFINE_WORKSPACE_ID")
    if ws:
        return ws
    cfg = os.path.expanduser("~/.config/affine-mcp/config")
    with open(cfg) as f:
        for line in f:
            line = line.strip()
            if line.startswith("AFFINE_WORKSPACE_ID="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("找不到 AFFINE_WORKSPACE_ID")


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    mode = sys.argv[1]
    m = MCP()
    m.start()
    try:
        if mode == "upload":
            ws = workspace_id()
            for path in sys.argv[2:]:
                data = open(path, "rb").read()
                ct = mimetypes.guess_type(path)[0] or "application/octet-stream"
                out = m.call("upload_blob", {
                    "workspaceId": ws,
                    "content": base64.b64encode(data).decode(),
                    "encoding": "base64",
                    "contentType": ct,
                    "filename": os.path.basename(path),
                })
                print(f"{os.path.basename(path)}\t{len(data)//1024}KB\t{out}")
        elif mode == "call":
            tool = sys.argv[2]
            args = json.load(open(sys.argv[3]))
            args.setdefault("workspaceId", workspace_id())
            print(m.call(tool, args))
        else:
            raise SystemExit(f"不認得的模式：{mode}")
    finally:
        m.close()


if __name__ == "__main__":
    main()
