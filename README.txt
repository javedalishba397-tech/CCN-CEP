MYDNS/1.1 - starter code (Python 3, standard library only; matplotlib optional for graph)

FILES
  protocol.py       shared wire contract (run `python protocol.py` for self-test)
  config.py         IPs, ports, timeouts  <- only file to edit when moving to 3 laptops
  auth_server.py    Host 3 - authoritative server
  resolver.py       Host 2 - caching resolver
  client.py         Host 1 - client + benchmark

RUN (3 terminals, in this order)
  python auth_server.py
  python resolver.py
  python client.py www.mydns.local        (run twice: 1st = MISS, 2nd = HIT)
  python client.py nope.mydns.local       (NXDOMAIN)
  python client.py --bench 10             (10 miss + 10 hit trials -> bench.csv, bench.png)

FAILURE DEMOS (R7)
  python resolver.py --drop 1             client->resolver datagram lost -> client retransmits after 2 s (RETRY flag)
  python auth_server.py --drop 1          resolver->auth datagram lost -> resolver replies SERVER_FAILURE after 1 s
  python auth_server.py --delay 300       slow authoritative server
  stop auth_server.py                     resolver replies SERVER_FAILURE after 1 s
  stop resolver.py                        client gives up after 2+4+8 = 14 s
  python resolver.py --ttl 10             shorter TTL for the freshness experiment

MOVING TO 3 LAPTOPS
  Edit config.py on each laptop: RESOLVER_IP = laptop-2 IPv4, AUTH_IP = laptop-3 IPv4
  (from `ipconfig`). Allow Python through the Windows firewall (Private network).
