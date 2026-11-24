# config.py - the ONLY file you edit when moving to 3 laptops.
# On one laptop: leave everything as 127.0.0.1.
# On 3 laptops: put the real IPs from `ipconfig` (IPv4 Address), e.g. "192.168.43.102".

RESOLVER_IP = "192.168.56.103"      # Host 2 (caching resolver)
RESOLVER_PORT = 5300
AUTH_IP = "192.168.56.102"          # Host 3 (authoritative server)
AUTH_PORT = 5301

BIND_IP = "0.0.0.0"            # servers listen on all interfaces (needed for other laptops)

CLIENT_TIMEOUT = 2.0           # seconds, doubles on every retry
CLIENT_ATTEMPTS = 3
UPSTREAM_TIMEOUT = 1.0         # resolver -> authoritative, seconds
UPSTREAM_ATTEMPTS = 1

NEG_TTL = 10                   # seconds, negative caching of NXDOMAIN
