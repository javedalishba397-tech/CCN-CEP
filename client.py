"""client.py - Host 1: lookups with stop-and-wait retransmission, plus the R6 benchmark.

Run:  python client.py www.mydns.local
      python client.py --bench 10          # 10 misses + 10 hits, mean/stdev, CSV + graph
"""
import argparse, csv, random, socket, statistics, time
import config
from protocol import *


def lookup(domain):
    """Returns (reply_dict_or_None, rtt_ms, attempts_used). Retries with doubling timeout."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    txid = random.randint(0, 65535)
    timeout = config.CLIENT_TIMEOUT
    t0 = time.perf_counter()
    try:
        for attempt in range(1, config.CLIENT_ATTEMPTS + 1):
            sock.sendto(pack_query(txid, domain, FLAG_RETRY if attempt > 1 else 0),
                        (config.RESOLVER_IP, config.RESOLVER_PORT))
            deadline = time.perf_counter() + timeout
            while True:
                left = deadline - time.perf_counter()
                if left <= 0:
                    break
                sock.settimeout(left)
                try:
                    data, _ = sock.recvfrom(512)
                except socket.timeout:
                    break
                try:
                    r = unpack(data)
                except ValueError:
                    continue
                if r["txid"] == txid:                      # ignore stale / foreign replies
                    return r, (time.perf_counter() - t0) * 1000, attempt
            timeout *= 2
        return None, (time.perf_counter() - t0) * 1000, config.CLIENT_ATTEMPTS
    finally:
        sock.close()


def show(domain):
    r, rtt, attempts = lookup(domain)
    if r is None:
        print("ERROR: no response from resolver after %d attempts (timeout)" % attempts)
    elif r["type"] == ERROR or r["status"] == SERVER_FAILURE:
        print("ERROR: %s (resolver could not reach the authoritative server)" % STATUS_NAMES[r["status"]])
    elif r["status"] == NXDOMAIN:
        print("%s: NXDOMAIN (name does not exist)  [%.2f ms]" % (domain, rtt))
    else:
        src = "CACHE HIT" if r["flags"] & FLAG_CACHED else "CACHE MISS (authoritative)"
        print("%s -> %s  ttl=%ds  %s  [%.2f ms, %d attempt(s)]" %
              (domain, ", ".join(r["ips"]), r["ttl"], src, rtt, attempts))


def bench(n):
    if n > 30:
        raise SystemExit("zone only has host01..host30; use n <= 30")
    miss, hit = [], []
    for i in range(1, n + 1):
        d = "host%02d.mydns.local" % i
        r1, t1, _ = lookup(d)          # first time -> should be a MISS
        r2, t2, _ = lookup(d)          # second time -> should be a HIT
        if not r1 or not r2:
            raise SystemExit("lookup failed - are the resolver and authoritative running?")
        if r1["flags"] & FLAG_CACHED:
            print("warning: %s was already cached (restart resolver for clean misses)" % d)
        miss.append(t1); hit.append(t2)
        print("%-22s miss %.3f ms | hit %.3f ms" % (d, t1, t2))
    def summ(x):
        return statistics.mean(x), (statistics.stdev(x) if len(x) > 1 else 0.0), min(x), max(x)
    print("\n%-6s %9s %9s %9s %9s" % ("", "mean", "stdev", "min", "max"))
    for name, x in (("MISS", miss), ("HIT", hit)):
        print("%-6s %9.3f %9.3f %9.3f %9.3f  (ms, n=%d)" % ((name,) + summ(x) + (len(x),)))
    with open("bench.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["trial", "miss_ms", "hit_ms"])
        for i, (a, b) in enumerate(zip(miss, hit), 1): w.writerow([i, a, b])
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        m, h = summ(miss), summ(hit)
        plt.bar(["Cache miss", "Cache hit"], [m[0], h[0]], yerr=[m[1], h[1]], capsize=6,
                color=["#e07a5f", "#81b29a"])
        plt.ylabel("RTT (ms)"); plt.title("MYDNS lookup RTT, n=%d" % n)
        plt.savefig("bench.png", dpi=150, bbox_inches="tight")
        print("saved bench.csv and bench.png")
    except ImportError:
        print("saved bench.csv (install matplotlib for the graph: pip install matplotlib)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("domain", nargs="?", help="name to look up")
    ap.add_argument("--bench", type=int, metavar="N", help="run N miss/hit trials")
    a = ap.parse_args()
    if a.bench:
        bench(a.bench)
    elif a.domain:
        show(a.domain)
    else:
        ap.print_help()
