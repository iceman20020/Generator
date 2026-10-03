import asyncio, socket

SERVICES = {22:"ssh",23:"telnet",21:"ftp",445:"smb",3389:"rdp",80:"http",8080:"http-alt",3306:"mysql",5432:"postgres",6379:"redis",27017:"mongo"}

async def grab_banner(host, port, timeout=2):
    try:
        r, w = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
        try:
            banner = await asyncio.wait_for(r.read(256), timeout)
        except asyncio.TimeoutError:
            banner = b""
        w.close()
        try: await w.wait_closed()
        except: pass
        return banner.decode(errors="ignore").strip()
    except Exception:
        return ""

async def scan_port(host, port, timeout, sem):
    async with sem:
        try:
            r, w = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
            w.close()
            try: await w.wait_closed()
            except: pass
            banner = await grab_banner(host, port, timeout)
            svc = SERVICES.get(port, "unknown")
            return (port, True, svc, banner)
        except Exception:
            return (port, False, None, "")

async def scan_host(host, ports, timeout=2, workers=200):
    sem = asyncio.Semaphore(workers)
    tasks = [scan_port(host, p, timeout, sem) for p in ports]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r[1]]

def scan(hosts, ports, timeout=2, workers=200):
    async def run():
        out = {}
        for h in hosts:
            out[h] = await scan_host(h, ports, timeout, workers)
        return out
    return asyncio.run(run())
