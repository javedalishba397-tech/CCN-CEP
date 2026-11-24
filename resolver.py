"""resolver.py - Host 2: caching resolver (TTL cache, negative caching, upstream timeout).

Run:  python resolver.py
      python resolver.py --ttl 10      # override every record's TTL (for the freshness experiment)
      python resolver.py --drop 1      # ignore the first client query (simulated loss -> client retransmits)
"""
import argparse, math, random, socket, threading, time
import config
from protocol import *

cache = {}                         # name -> (ips, status, expiry_time)
lock = threading.Lock()
TTL_OVERRIDE = None
TO_DROP = 0


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def ask_upstream(domain):
    """Query the authoritative server. Returns parsed reply dict or None on timeout."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(config.UPSTREAM_TIMEOUT)
    txid = random.randint(0, 65535)
    try:
        for attempt in range(1, config.UPSTREAM_ATTEMPTS + 1):
            sock.sendto(pack_query(txid, domain, FLAG_RETRY if attempt > 1 else 0),
                        (config.AUTH_IP, config.AUTH_PORT))
            try:
                while True:
                    data, _ = sock.recvfrom(512)
                    try:
                        r = unpack(data)
                    except ValueError:
                        continue
                    if r["txid"] == txid:
                        return r
            except socket.timeout:
                log("UPSTREAM TIMEOUT for %s (attempt %d/%d)" % (domain, attempt, config.UPSTREAM_ATTEMPTS))
        return None
    finally:
        sock.close()


def handle(sock, data, addr):
    try:
        q = unpack(data)
        if q["type"] != QUERY:
            raise ValueError("not a QUERY")
    except ValueError as e:
        log("FORMAT_ERROR from %s: %s" % (addr, e))
        sock.sendto(pack_error(0, "?", FORMAT_ERROR), addr)
        return
    name, txid = q["domain"].lower(), q["txid"]
    now = time.time()
    with lock:
        entry = cache.get(name)
        if entry and entry[2] <= now:
            del cache[name]
            log("EXPIRED %s" % name)
            entry = None
    if entry:                                              # ---- cache HIT
        ips, status, expiry = entry
        remaining = max(1, int(math.ceil(expiry - now)))
        log("HIT  %s (remaining ttl %ds) txid=%d" % (name, remaining, txid))
        sock.sendto(pack_response(txid, name, ips, remaining, FLAG_CACHED, status), addr)
        return
    log("MISS %s -> asking authoritative txid=%d" % (name, txid))   # ---- cache MISS
    r = ask_upstream(name)
    if r is None:
        log("SERVER_FAILURE for %s (authoritative unreachable)" % name)
        sock.sendto(pack_error(txid, name, SERVER_FAILURE), addr)
        return
    ttl = TTL_OVERRIDE if TTL_OVERRIDE is not None else r["ttl"]
    if r["type"] == RESPONSE and ttl > 0:
        with lock:
            cache[name] = (r["ips"], r["status"], time.time() + ttl)
        log("CACHED %s for %ds (status %s)" % (name, ttl, STATUS_NAMES.get(r["status"])))
    sock.sendto(pack_response(txid, name, r["ips"], ttl, r["flags"] & FLAG_AA, r["status"]), addr)


def main():
    global TTL_OVERRIDE, TO_DROP
    ap = argparse.ArgumentParser()
    ap.add_argument("--ttl", type=int, default=None, help="override record TTL (seconds)")
    ap.add_argument("--drop", type=int, default=0, help="ignore the next N client queries")
    a = ap.parse_args()
    TTL_OVERRIDE, TO_DROP = a.ttl, a.drop
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((config.BIND_IP, config.RESOLVER_PORT))
    log("RESOLVER listening on %s:%d, upstream %s:%d" %
        (config.BIND_IP, config.RESOLVER_PORT, config.AUTH_IP, config.AUTH_PORT))
    while True:
        data, addr = sock.recvfrom(512)
        if TO_DROP > 0:
            TO_DROP -= 1
            log("DROPPED a client datagram from %s (simulated loss)" % (addr,))
            continue
        threading.Thread(target=handle, args=(sock, data, addr), daemon=True).start()


if __name__ == "__main__":
    main()
