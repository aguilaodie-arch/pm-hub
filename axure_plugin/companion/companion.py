"""
本地助手（companion）参考实现 —— 用于把 Axure 生成的原型自动打包并上传到后端。

定位：Axure 插件运行在沙箱里，无法直接读取「生成 HTML」落盘的文件。
所以由这个常驻小服务来桥接：插件把「Axure 生成目录路径」告诉它，
它负责打包 ZIP 并调用后端的发布接口。

运行：
    python companion.py --port 8765
然后在 Axure 插件里把上传目标指向 http://localhost:8765/publish?sid=<SprintID>

注意：本文件是「参考骨架」，演示了桥接思路。生产化时需要根据你团队
实际的 Axure 生成目录、鉴权方式做对接（例如插件先拿到登录态再转发）。
"""
import argparse
import io
import os
import zipfile

import requests
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 后端地址（内部平台）
BACKEND_BASE = os.environ.get("BACKEND_BASE", "http://localhost:8000")
# 简单约定：本地助手与浏览器共用同一套登录 Cookie/Token，这里用 header 透传
AUTH_HEADER = os.environ.get("AUTH_HEADER", "X-Auth-Token")


@app.post("/publish")
def publish(sid: int = Query(...), axure_dir: str = Query(...),
            title: str = Query(""), token: str = Query("")):
    """接收 Axure 生成目录路径，打包后转发给后端发布接口。"""
    if not os.path.isdir(axure_dir):
        raise HTTPException(400, f"Axure 生成目录不存在: {axure_dir}")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(axure_dir):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, axure_dir)
                z.write(full, rel)
    buf.seek(0)

    headers = {"X-Auth-Token": token} if token else {}
    r = requests.post(
        f"{BACKEND_BASE}/api/sprints/{sid}/publish",
        headers=headers,
        files={"file": ("prototype.zip", buf, "application/zip")},
        data={"title": title},
        timeout=120,
    )
    if not r.ok:
        raise HTTPException(500, f"后端返回: {r.status_code} {r.text}")
    return r.json()


if __name__ == "__main__":
    import uvicorn
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=8765)
    args = p.parse_args()
    uvicorn.run(app, host="127.0.0.1", port=args.port)
