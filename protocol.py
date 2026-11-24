"""protocol.py - MYDNS/1.1 wire contract shared by client, resolver and authoritative server.

Header (8 bytes, struct "!HBBBBH", network byte order):
    Transaction ID (16) | Msg Type (8) | Flags (8) | Status (8) | Answer Count (8) | TTL (16)
Payload:
    1 byte domain length + ASCII domain name  [+ Answer Count x 4-byte IPv4, responses only]
"""
import socket
import struct

HEADER_FMT = "!HBBBBH"
HEADER_LEN = struct.calcsize(HEADER_FMT)      # 8

# Message types
QUERY, RESPONSE, ERROR = 0x01, 0x02, 0x03
# Status codes
SUCCESS, NXDOMAIN, SERVER_FAILURE, FORMAT_ERROR = 0, 1, 2, 3
STATUS_NAMES = {0: "SUCCESS", 1: "NXDOMAIN", 2: "SERVER_FAILURE", 3: "FORMAT_ERROR"}
# Flags (bit mask)
FLAG_AA, FLAG_CACHED, FLAG_RETRY = 0x01, 0x02, 0x04


def _name_bytes(domain):
    name = domain.encode("ascii")
    if not 0 < len(name) < 256:
        raise ValueError("domain length must be 1..255")
    return bytes([len(name)]) + name


def pack_query(txid, domain, flags=0):
    return struct.pack(HEADER_FMT, txid, QUERY, flags, 0, 0, 0) + _name_bytes(domain)


def pack_response(txid, domain, ips, ttl, flags=0, status=SUCCESS):
    """RESPONSE (also used for NXDOMAIN with ips=[])."""
    body = _name_bytes(domain) + b"".join(socket.inet_aton(ip) for ip in ips)
    return struct.pack(HEADER_FMT, txid, RESPONSE, flags, status, len(ips), min(ttl, 65535)) + body


def pack_error(txid, domain, status):
    """ERROR message (SERVER_FAILURE, FORMAT_ERROR). Domain may be empty -> sent as '?'."""
    return (struct.pack(HEADER_FMT, txid, ERROR, 0, status, 0, 0)
            + _name_bytes(domain or "?"))


def unpack(data):
    """Parse a packet into a dict. Raises ValueError if the packet is malformed."""
    if len(data) < HEADER_LEN + 1:
        raise ValueError("packet too short")
    txid, mtype, flags, status, count, ttl = struct.unpack(HEADER_FMT, data[:HEADER_LEN])
    if mtype not in (QUERY, RESPONSE, ERROR):
        raise ValueError("unknown message type %d" % mtype)
    nlen = data[HEADER_LEN]
    start, end = HEADER_LEN + 1, HEADER_LEN + 1 + nlen
    if nlen == 0 or len(data) < end:
        raise ValueError("bad domain length")
    try:
        domain = data[start:end].decode("ascii")
    except UnicodeDecodeError:
        raise ValueError("domain is not ASCII")
    rest = data[end:]
    if mtype == RESPONSE:
        if len(rest) != count * 4:
            raise ValueError("answer count does not match payload")
        ips = [socket.inet_ntoa(rest[i:i + 4]) for i in range(0, len(rest), 4)]
    else:
        if rest:
            raise ValueError("unexpected trailing bytes")
        ips = []
    return {"txid": txid, "type": mtype, "flags": flags, "status": status,
            "ttl": ttl, "domain": domain, "ips": ips}


if __name__ == "__main__":                       # self-test: python protocol.py
    q = pack_query(1234, "www.mydns.local", FLAG_RETRY)
    assert unpack(q)["domain"] == "www.mydns.local" and unpack(q)["flags"] == FLAG_RETRY
    r = pack_response(1234, "www.mydns.local", ["10.0.0.5", "10.0.0.6"], 60, FLAG_AA | FLAG_CACHED)
    m = unpack(r)
    assert m["ips"] == ["10.0.0.5", "10.0.0.6"] and m["ttl"] == 60 and m["status"] == SUCCESS
    e = unpack(pack_error(7, "x.local", SERVER_FAILURE))
    assert e["type"] == ERROR and e["status"] == SERVER_FAILURE
    for bad in (b"", b"\x00" * 8, q[:-3]):
        try:
            unpack(bad); raise SystemExit("should have failed")
        except ValueError:
            pass
    print("query bytes:", len(q), "| response bytes:", len(r), "| protocol.py self-test OK")
