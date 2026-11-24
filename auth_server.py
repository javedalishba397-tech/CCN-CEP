"""auth_server.py - Host 3: authoritative server holding the master zone.

Run:  python auth_server.py
Testing switches (for the R7 failure demo):
      python auth_server.py --drop 1        # silently ignore the next 1 query (packet loss)
      python auth_server.py --delay 300     # wait 300 ms before every reply
"""
import argparse, socket, time
import config
from protocol import *

# zone: name -> (list of IPv4, TTL seconds)
ZONE = {
    "www.mydns.local":  (["10.0.0.5"], 60),
    "mail.mydns.local": (["10.0.0.6"], 60),
    "ns.mydns.local":   (["10.0.0.7", "10.0.0.8"], 120),
}
for i in range(1, 31):                       # host01..host30: used by the benchmark (one fresh miss each)
    ZONE["host%02d.mydns.local" % i] = (["10.0.1.%d" % i], 60)


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", type=int, default=0, help="ignore the next N queries")
    ap.add_argument("--delay", type=int, default=0, help="reply delay in ms")
    args = ap.parse_args()
    to_drop = args.drop

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((config.BIND_IP, config.AUTH_PORT))
    log("AUTH listening on %s:%d (%d records)" % (config.BIND_IP, config.AUTH_PORT, len(ZONE)))
    while True:
        data, addr = sock.recvfrom(512)
        try:
            q = unpack(data)
            if q["type"] != QUERY:
                raise ValueError("not a QUERY")
        except ValueError as e:
            log("FORMAT_ERROR from %s: %s" % (addr, e))
            sock.sendto(pack_error(0, "?", FORMAT_ERROR), addr)
            continue
        if to_drop > 0:
            to_drop -= 1
            log("DROPPED query %s txid=%d (simulated loss)" % (q["domain"], q["txid"]))
            continue
        name = q["domain"].lower()
        if name in ZONE:
            ips, ttl = ZONE[name]
            reply = pack_response(q["txid"], name, ips, ttl, FLAG_AA)
            log("ANSWER %s -> %s ttl=%d txid=%d" % (name, ips, ttl, q["txid"]))
        else:
            reply = pack_response(q["txid"], name, [], config.NEG_TTL, FLAG_AA, NXDOMAIN)
            log("NXDOMAIN %s txid=%d" % (name, q["txid"]))
        if args.delay:
            time.sleep(args.delay / 1000.0)
        sock.sendto(reply, addr)


if __name__ == "__main__":
    main()
