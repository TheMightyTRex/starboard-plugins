"""The kinds of check (Uptime and status 2.0.0), each with Python's standard library only, and the one-line way people
write a check.

    http      a web address answers (any answer under 500, as Outside services 1.x did)
    keyword   a web page answers and has (or, with "without", has not) some words
    tcp       a port takes a connection, such as 192.168.1.5:445
    ping      a computer answers ICMP echo; where the container may not send ICMP, a TCP knock on 443, 80, 22 and 53
    dns       a name has a record of a type, optionally with a given value, from a given server
    cert      a certificate that is still good, and how many days it has left (reads it, sends no web request)
    push      a heartbeat: something else calls the check's secret address, and a missed grace time means down

Every function here takes its network calls through module-level names (socket, ssl, urllib) so the tests replace them.
A result is {"up": bool, "ms": number or None, "said": short words}.
"""
import errno
import os
import random
import re
import secrets
import shlex
import socket
import ssl
import struct
import time
import urllib.error
import urllib.parse
import urllib.request

KINDS = ("http", "keyword", "tcp", "ping", "dns", "cert", "push")
KIND_WORDS = {"http": "Web address", "keyword": "Words on a page", "tcp": "Port", "ping": "Ping", "dns": "DNS record",
              "cert": "Certificate", "push": "Heartbeat"}
DNS_TYPES = {"A": 1, "NS": 2, "CNAME": 5, "MX": 15, "TXT": 16, "AAAA": 28}
TIMEOUT = 8
PAGE_LIMIT = 512 * 1024  # the most of a page read to find words in
AGENT = "Starboard plug-in (Uptime and status)"
KNOCK_PORTS = (443, 80, 22, 53)
MIN_EVERY, MAX_EVERY = 20, 24 * 3600
DEFAULT_GRACE = 3600
CERT_CHECK_EVERY = 6 * 3600  # a certificate changes slowly: read it four times a day unless told otherwise


class LineError(ValueError):
    """A check written in a way it cannot be read: the message says what to change."""


# Reading a check from one line ----------------------------------------------------------------------------------------

def _seconds(text):
    m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(s|sec|secs|seconds?|m|min|mins|minutes?|h|hours?|d|days?)?", text.strip().lower())
    if not m:
        raise LineError(f"\"{text}\" is not a time. Write it as 30s, 5m, 2h or 1d")
    n, unit = float(m.group(1)), (m.group(2) or "m")[0]
    return int(n * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit])


def _host_port(text):
    m = re.fullmatch(r"\[([0-9a-fA-F:.]+)\]:(\d{1,5})|([^\s:/\[\]]+):(\d{1,5})", text)
    if not m:
        raise LineError(f"\"{text}\" is not a computer and port. Write it as 192.168.1.5:445 or nas.home:22")
    host, port = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
    if not 1 <= int(port) <= 65535:
        raise LineError(f"Port {port} is not between 1 and 65535")
    return host, int(port)


def _url(text):
    u = urllib.parse.urlsplit(text)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise LineError(f"\"{text}\" is not a web address. Start it with http:// or https://")
    return text


def _host(text):
    if not re.fullmatch(r"[A-Za-z0-9.:_-]{1,253}", text) or "://" in text:
        raise LineError(f"\"{text}\" is not a computer's name or address, such as 192.168.1.1 or nas.home")
    return text


def parse(line, default_every=300):
    """One line, such as `Router: ping 192.168.1.1 in Home #network every 1m`, to a check (without its id).
    Raises LineError with what to change."""
    line = " ".join(str(line or "").split())
    if not line:
        raise LineError("Write the check, such as Router: ping 192.168.1.1")
    if len(line) > 500:
        raise LineError("Keep a check to 500 characters")
    name = ""
    head, sep, rest = line.partition(": ")
    if sep and "://" not in head and head.strip():
        name, line = head.strip(), rest
    try:
        words = shlex.split(line)
    except ValueError:
        raise LineError("A quote mark is not closed. Put the words between two \" marks") from None
    if not words:
        raise LineError("Write what to check after the name, such as ping 192.168.1.1")
    kind = words[0].lower()
    if kind in KINDS:
        words = words[1:]
    elif re.match(r"^https?://", words[0]):
        kind = "http"
    elif re.fullmatch(r"\[[0-9a-fA-F:.]+\]:\d+|[^\s:/\[\]]+:\d+", words[0]):
        kind = "tcp"
    else:
        kind = "ping"
    c = {"name": name, "kind": kind, "group": "", "tags": [], "every": CERT_CHECK_EVERY if kind == "cert" else int(default_every),
         "on": True}
    pos = []
    i = 0
    while i < len(words):
        w, low = words[i], words[i].lower()
        nxt = words[i + 1] if i + 1 < len(words) else None
        if low == "in" and nxt is not None:
            c["group"] = nxt[:40]
            i += 2
        elif w.startswith("#") and len(w) > 1:
            c["tags"].append(w[1:][:30])
            i += 1
        elif low == "every" and nxt is not None:
            c["every"] = _seconds(nxt)
            i += 2
        elif low == "grace" and nxt is not None and kind == "push":
            c["grace"] = _seconds(nxt)
            i += 2
        elif low == "type" and nxt is not None and kind == "dns":
            c["record"] = nxt.upper()
            i += 2
        elif low == "is" and nxt is not None and kind == "dns":
            c["expect"] = nxt
            i += 2
        elif low == "at" and nxt is not None and kind == "dns":
            c["server"] = _host(nxt)
            i += 2
        elif low == "without" and kind == "keyword":
            c["absent"] = True
            i += 1
        elif low == "tls" and kind == "tcp":
            c["tls"] = True
            i += 1
        else:
            pos.append(w)
            i += 1
    if not MIN_EVERY <= c["every"] <= MAX_EVERY:
        raise LineError("Check every 20 seconds at the most often, and once a day at the least")
    if kind == "push":
        if pos:
            raise LineError("A heartbeat needs no address: Starboard gives it one. Write it as Backup: push grace 25h")
        c["grace"] = c.get("grace", DEFAULT_GRACE)
        if not 60 <= c["grace"] <= 31 * 86400:
            raise LineError("Give a heartbeat a grace time from 1 minute to 31 days")
        c["target"] = ""
        c["token"] = secrets.token_urlsafe(18)
    elif not pos:
        raise LineError(f"Write what to check after {kind}, such as {EXAMPLES[kind]}")
    elif kind in ("http", "keyword"):
        c["target"] = _url(pos[0])
        if kind == "keyword":
            if len(pos) < 2:
                raise LineError("Put the words to find after the address, between quote marks: keyword https://example.org \"In stock\"")
            c["words"] = " ".join(pos[1:])[:200]
        elif len(pos) > 1:
            raise LineError(f"\"{pos[1]}\" is not something a web address check takes")
    elif kind == "tcp":
        c["target"] = "%s:%d" % _host_port(pos[0]) if not pos[0].startswith("[") else pos[0]
        _host_port(c["target"])
    elif kind == "ping":
        c["target"] = _host(pos[0])
    elif kind == "cert":
        if len(pos) > 1:
            raise LineError(f"\"{pos[1]}\" is not something a certificate check takes")
        word = pos[0]
        if re.match(r"^https?://", word):
            u = urllib.parse.urlsplit(word)
            word = f"{u.hostname}:{u.port or 443}" if u.hostname else word
        c["target"] = "%s:%d" % _host_port(word) if re.search(r":\d+$", word) and not word.startswith("[") else \
            (word if word.startswith("[") else "%s:443" % _host(word))
        _host_port(c["target"])
    elif kind == "dns":
        c["target"] = _host(pos[0])
        if len(pos) > 1 and pos[1].upper() in DNS_TYPES:
            c["record"] = pos[1].upper()
        c["record"] = c.get("record", "A")
        if c["record"] not in DNS_TYPES:
            raise LineError(f"DNS checks know {', '.join(DNS_TYPES)}, not {c['record']}")
    c["name"] = (c["name"] or _short(c))[:60]
    return c


EXAMPLES = {"http": "http https://example.org", "keyword": "keyword https://example.org \"In stock\"",
            "tcp": "tcp 192.168.1.5:445", "ping": "ping 192.168.1.1", "dns": "dns example.org A", "cert": "cert example.org", "push": "push grace 25h"}


def _short(c):
    if c["kind"] in ("http", "keyword"):
        return urllib.parse.urlsplit(c["target"]).hostname or c["target"]
    return c["target"] or "Heartbeat"


def line(c):
    """The check written back as one line, so Change can show it as it is."""
    parts = [f"{c['name']}: {c['kind']}"]
    if c["kind"] in ("http", "keyword", "tcp", "ping", "dns", "cert"):
        parts.append(c["target"])
    if c["kind"] == "keyword":
        if c.get("absent"):
            parts.append("without")
        parts.append(shlex.quote(c["words"]) if " " in c["words"] else c["words"])
    if c["kind"] == "dns":
        parts.append(c.get("record", "A"))
        if c.get("expect"):
            parts += ["is", c["expect"]]
        if c.get("server"):
            parts += ["at", c["server"]]
    if c["kind"] == "tcp" and c.get("tls"):
        parts.append("tls")
    if c["kind"] == "push":
        parts += ["grace", _span(c.get("grace", DEFAULT_GRACE))]
    if c.get("group"):
        parts += ["in", shlex.quote(c["group"]) if " " in c["group"] else c["group"]]
    parts += [f"#{t}" for t in c.get("tags") or []]
    if c["kind"] != "push":
        parts += ["every", _span(c.get("every", 300))]
    return " ".join(parts)


def _span(seconds):
    for unit, n in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds % n == 0:
            return f"{seconds // n}{unit}"
    return f"{seconds}s"


# Running a check ------------------------------------------------------------------------------------------------------

def run(c, now=None):
    """Runs check c once (not push: that is worked out from its last call)."""
    fn = {"http": check_http, "keyword": check_http, "tcp": check_tcp, "ping": check_ping, "dns": check_dns,
          "cert": check_cert}[c["kind"]]
    started = time.monotonic()
    try:
        out = fn(c)
    except Exception as e:  # noqa: BLE001 - every failure is a down with words, never a stop
        out = {"up": False, "said": _words(e)}
    if out.get("ms") is None and out.get("up"):
        out["ms"] = round((time.monotonic() - started) * 1000, 1)
    return out


def _words(e):
    if isinstance(e, TimeoutError):
        return "No answer in 8 seconds"
    if isinstance(e, socket.gaierror):
        return "The name was not found"
    if isinstance(e, ConnectionRefusedError):
        return "The connection was refused"
    if isinstance(e, urllib.error.URLError) and getattr(e, "reason", None) is not None and not isinstance(e.reason, str):
        return _words(e.reason)
    if isinstance(e, OSError) and e.errno in (errno.EHOSTUNREACH, errno.ENETUNREACH):
        return "It cannot be reached from the server"
    return str(e)[:120] or type(e).__name__


def _unverified():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def check_http(c):
    """Up when it answers under 500 (a sign-in page or 404 still means it answers). A keyword check also needs an answer
    under 400 with the words (or, with absent, without them). Certificates are not checked here, so a home device with
    its own certificate still counts as up: the certificate check says whether it is trusted."""
    req = urllib.request.Request(c["target"], headers={"User-Agent": AGENT, "Accept": "text/html,*/*"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_unverified()) as r:  # an address the owner gave  # nosec B310
            status, body = r.status, (r.read(PAGE_LIMIT) if c["kind"] == "keyword" else r.read(1024))
    except urllib.error.HTTPError as e:
        status, body = e.code, b""
    ms = round((time.monotonic() - started) * 1000, 1)
    if c["kind"] == "keyword":
        if status >= 400:
            return {"up": False, "ms": ms, "said": f"It answered with error {status}"}
        found = c["words"].lower() in body.decode("utf-8", "replace").lower()
        if found == bool(c.get("absent")):
            return {"up": False, "ms": ms, "said": f"\"{c['words']}\" is {'on' if found else 'not on'} the page"}
        return {"up": True, "ms": ms, "said": f"\"{c['words']}\" is {'not on' if c.get('absent') else 'on'} the page"}
    if status >= 500:
        return {"up": False, "ms": ms, "said": f"It answered with error {status}"}
    return {"up": True, "ms": ms, "said": f"It answered ({status})"}


def check_tcp(c):
    host, port = _host_port(c["target"])
    started = time.monotonic()
    with socket.create_connection((host, port), timeout=TIMEOUT):
        pass
    return {"up": True, "ms": round((time.monotonic() - started) * 1000, 1), "said": f"Port {port} takes connections"}


def _checksum(data):
    if len(data) % 2:
        data += b"\0"
    s = sum(struct.unpack(f"!{len(data) // 2}H", data))
    s = (s >> 16) + (s & 0xFFFF)
    s += s >> 16
    return ~s & 0xFFFF


def _address(host):
    infos = socket.getaddrinfo(host, None, type=socket.SOCK_DGRAM)
    infos.sort(key=lambda i: i[0] != socket.AF_INET)  # IPv4 first
    return infos[0][0], infos[0][4][0]


def icmp(host, timeout=TIMEOUT):
    """ms for one ICMP echo, with an unprivileged ping socket (Docker allows these for every group since 20.10, so no
    capability is needed). Raises PermissionError where the container may not send ICMP, TimeoutError when no answer."""
    family, addr = _address(host)
    v6 = family == socket.AF_INET6
    s = socket.socket(family, socket.SOCK_DGRAM, socket.IPPROTO_ICMPV6 if v6 else socket.IPPROTO_ICMP)
    try:
        s.settimeout(timeout)
        seq = random.randint(1, 0xFFFF)
        payload = b"starboard-uptime"
        head = struct.pack("!BBHHH", 128 if v6 else 8, 0, 0, 0, seq)
        packet = struct.pack("!BBHHH", 128 if v6 else 8, 0, 0 if v6 else _checksum(head + payload), 0, seq) + payload
        started = time.monotonic()
        s.sendto(packet, (addr, 0))
        while True:
            left = timeout - (time.monotonic() - started)
            if left <= 0:
                raise TimeoutError("no echo reply")
            s.settimeout(left)
            data, _ = s.recvfrom(1024)
            if len(data) >= 8 and data[0] == (129 if v6 else 0) and struct.unpack("!H", data[6:8])[0] == seq:
                return round((time.monotonic() - started) * 1000, 1)
    finally:
        s.close()


def knock(host, ports=KNOCK_PORTS, timeout=3):
    """ms until the computer answers a TCP connection on any of ports, refused or not: a refusal is an answer."""
    for port in ports:
        started = time.monotonic()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                pass
        except ConnectionRefusedError:
            pass
        except OSError:
            continue
        return round((time.monotonic() - started) * 1000, 1), port
    raise TimeoutError("no answer on ports " + ", ".join(map(str, ports)))


def check_ping(c):
    try:
        return {"up": True, "ms": icmp(c["target"]), "said": "It answers ping"}
    except socket.gaierror:
        raise
    except TimeoutError:
        return {"up": False, "said": "No answer to ping in 8 seconds"}
    except OSError as e:
        if e.errno not in (errno.EPERM, errno.EACCES, errno.EPROTONOSUPPORT, errno.EAFNOSUPPORT, errno.ESOCKTNOSUPPORT):
            raise
    ms, port = knock(c["target"])  # the container may not send ICMP: knock on common ports instead
    return {"up": True, "ms": ms, "said": f"It answers on port {port} (ping is not allowed here, so a port was tried)"}


# DNS, with the standard library: one query over UDP --------------------------------------------------------------------

def nameserver():
    try:
        with open(os.environ.get("RESOLV_CONF", "/etc/resolv.conf"), encoding="utf-8") as f:
            for row in f:
                parts = row.split()
                if len(parts) >= 2 and parts[0] == "nameserver":
                    return parts[1]
    except OSError:
        pass
    return "127.0.0.11"


def dns_query(name, rtype, qid):
    q = b"".join(bytes([len(p)]) + p.encode("idna") for p in name.rstrip(".").split(".") if p) + b"\0"
    return struct.pack("!HHHHHH", qid, 0x0100, 1, 0, 0, 0) + q + struct.pack("!HH", rtype, 1)


def _name(msg, i, depth=0):
    labels = []
    while True:
        if i >= len(msg) or depth > 20:
            raise ValueError("a broken DNS answer")
        n = msg[i]
        if n == 0:
            return ".".join(labels), i + 1
        if n & 0xC0 == 0xC0:
            ptr = struct.unpack("!H", msg[i:i + 2])[0] & 0x3FFF
            rest, _ = _name(msg, ptr, depth + 1)
            return ".".join(labels + ([rest] if rest else [])), i + 2
        labels.append(msg[i + 1:i + 1 + n].decode("ascii", "replace"))
        i += 1 + n


RCODES = {1: "The DNS server could not read the question", 2: "The DNS server failed", 3: "The name does not exist",
          5: "The DNS server refused"}


def dns_answers(msg, qid, rtype):
    """The values of the answers of type rtype, as text."""
    if len(msg) < 12:
        raise ValueError("a broken DNS answer")
    rid, flags, qd, an, _, _ = struct.unpack("!HHHHHH", msg[:12])
    if rid != qid:
        raise ValueError("a DNS answer to another question")
    if flags & 0x0F:
        raise LookupError(RCODES.get(flags & 0x0F, f"The DNS server answered with error {flags & 0x0F}"))
    i = 12
    for _ in range(qd):
        _, i = _name(msg, i)
        i += 4
    out = []
    for _ in range(an):
        _, i = _name(msg, i)
        t, _, _, size = struct.unpack("!HHIH", msg[i:i + 10])
        i += 10
        data, start = msg[i:i + size], i
        i += size
        if t != rtype:
            continue
        if t == 1:
            out.append(socket.inet_ntop(socket.AF_INET, data))
        elif t == 28:
            out.append(socket.inet_ntop(socket.AF_INET6, data))
        elif t in (2, 5):
            out.append(_name(msg, start)[0])
        elif t == 15:
            out.append(_name(msg, start + 2)[0])
        elif t == 16:
            j, words = 0, []
            while j < len(data):
                words.append(data[j + 1:j + 1 + data[j]].decode("utf-8", "replace"))
                j += 1 + data[j]
            out.append("".join(words))
    return out


def check_dns(c):
    rtype = DNS_TYPES[c.get("record", "A")]
    server = c.get("server") or nameserver()
    qid = random.randint(0, 0xFFFF)
    family = socket.AF_INET6 if ":" in server else socket.AF_INET
    s = socket.socket(family, socket.SOCK_DGRAM)
    try:
        s.settimeout(TIMEOUT)
        started = time.monotonic()
        s.connect((server, 53))  # connected, so a server that is not there is refused at once, not after 8 seconds
        s.send(dns_query(c["target"], rtype, qid))
        msg = s.recv(4096)
        ms = round((time.monotonic() - started) * 1000, 1)
    finally:
        s.close()
    try:
        values = dns_answers(msg, qid, rtype)
    except LookupError as e:
        return {"up": False, "ms": ms, "said": str(e)}
    record = c.get("record", "A")
    if not values:
        return {"up": False, "ms": ms, "said": f"No {record} record"}
    if c.get("expect"):
        want = c["expect"].rstrip(".").lower()
        if want not in [v.rstrip(".").lower() for v in values]:
            return {"up": False, "ms": ms, "said": f"{record} is {', '.join(values[:3])}, not {c['expect']}"}
    return {"up": True, "ms": ms, "said": f"{record} {', '.join(values[:3])}"[:120]}


# Heartbeats ------------------------------------------------------------------------------------------------------------

def check_push(c, last, now=None):
    """A heartbeat is up while its last call is within its grace time. `last` is {"at": seconds, "down": bool, "said"}."""
    now = time.time() if now is None else now
    if not last or not last.get("at"):
        return {"up": None, "said": "Waiting for the first call"}
    if last.get("down"):
        return {"up": False, "said": ("It said it is down: " + last["said"]) if last.get("said") else "It said it is down"}
    gone = now - last["at"]
    if gone > c.get("grace", DEFAULT_GRACE):
        return {"up": False, "said": f"No call for {_span_words(gone)}"}
    return {"up": True, "said": f"Called {_span_words(gone)} ago"}


def _span_words(seconds):
    seconds = int(seconds)
    if seconds < 90:
        return f"{seconds} seconds"
    if seconds < 90 * 60:
        return f"{round(seconds / 60)} minutes"
    if seconds < 36 * 3600:
        return f"{round(seconds / 3600)} hours"
    return f"{round(seconds / 86400)} days"


# Certificates: the date it runs out and the names it was issued for, with no package to read X.509 -------------------

def _tlv(b, i):
    tag, size = b[i], b[i + 1]
    i += 2
    if size & 0x80:
        n = size & 0x7F
        size = int.from_bytes(b[i:i + n], "big")
        i += n
    return tag, i, i + size


def _children(b, start, end):
    out = []
    while start < end:
        tag, s, e = _tlv(b, start)
        out.append((tag, s, e))
        start = e
    return out


def _when(tag, raw):
    text = raw.decode("ascii")
    fmt = "%y%m%d%H%M%SZ" if tag == 0x17 else "%Y%m%d%H%M%SZ"
    import calendar
    return calendar.timegm(time.strptime(text, fmt))


OID_CN = bytes.fromhex("550403")
OID_O = bytes.fromhex("55040a")
OID_SAN = bytes.fromhex("551d11")


def _names(b, start, end):
    """{"CN": ..., "O": ...} from a Name."""
    out = {}
    for _, s, e in _children(b, start, end):  # each SET
        for _, s2, e2 in _children(b, s, e):  # each SEQUENCE
            parts = _children(b, s2, e2)
            if len(parts) >= 2:
                oid = b[parts[0][1]:parts[0][2]]
                value = b[parts[1][1]:parts[1][2]].decode("utf-8", "replace")
                if oid == OID_CN:
                    out["CN"] = value
                elif oid == OID_O:
                    out["O"] = value
    return out


def read_cert(der):
    """{"not_after": seconds, "subject": common name, "names": [names it is for], "issuer": words} from DER."""
    _, s, e = _tlv(der, 0)
    tbs = _children(der, *_tlv(der, s)[1:])
    k = 1 if tbs[0][0] == 0xA0 else 0  # the version is optional
    issuer, validity, subject = tbs[k + 2], tbs[k + 3], tbs[k + 4]
    times = _children(der, validity[1], validity[2])
    not_after = _when(times[1][0], der[times[1][1]:times[1][2]])
    sub = _names(der, subject[1], subject[2])
    iss = _names(der, issuer[1], issuer[2])
    names = []
    for tag, xs, _xe in tbs[k + 6:]:
        if tag != 0xA3:
            continue
        for _, es, ee in _children(der, *_tlv(der, xs)[1:]):
            parts = _children(der, es, ee)
            if der[parts[0][1]:parts[0][2]] != OID_SAN:
                continue
            octet = parts[-1]
            for t, ns, ne in _children(der, *_tlv(der, octet[1])[1:]):
                if t == 0x82:
                    names.append(der[ns:ne].decode("ascii", "replace"))
                elif t == 0x87 and ne - ns in (4, 16):
                    names.append(socket.inet_ntop(socket.AF_INET if ne - ns == 4 else socket.AF_INET6, der[ns:ne]))
    if not names and sub.get("CN"):
        names = [sub["CN"]]
    return {"not_after": not_after, "subject": sub.get("CN", ""), "names": names[:20],
            "issuer": iss.get("O") or iss.get("CN") or ""}


def check_cert(c):
    """Up while the certificate can be read, is trusted and has not run out. The days left are in "said"; the alert some
    days before the end is Starboard's, raised from the "cert" fields this returns (see app.run_one)."""
    host, port = _host_port(c["target"])
    cert = fetch_cert(host, port)
    left = int((cert["not_after"] - time.time()) // 86400)
    if left < 0:
        return {"up": False, "said": "The certificate has run out", "cert": cert}
    if not cert.get("trusted"):
        return {"up": False, "said": f"The certificate is not trusted: {cert.get('why') or 'not trusted'}", "cert": cert}
    return {"up": True, "said": f"{left} day{'s' if left != 1 else ''} left", "cert": cert}


def cert_target(c):
    """(host, port) whose certificate to read, or None: https addresses, and ports checked with tls."""
    if c["kind"] in ("http", "keyword"):
        u = urllib.parse.urlsplit(c["target"])
        return (u.hostname, u.port or 443) if u.scheme == "https" else None
    if c["kind"] in ("cert",) or (c["kind"] == "tcp" and c.get("tls")):
        return _host_port(c["target"])
    return None


def fetch_cert(host, port, timeout=TIMEOUT):
    """The certificate at host:port: read_cert's fields with "trusted" and, when not trusted, "why"."""
    trusted, why = True, ""
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock, ctx.wrap_socket(sock, server_hostname=host) as tls:
            der = tls.getpeercert(binary_form=True)
    except ssl.SSLCertVerificationError as e:
        trusted, why = False, (getattr(e, "verify_message", "") or "not trusted")[:80]
        with socket.create_connection((host, port), timeout=timeout) as sock, \
                _unverified().wrap_socket(sock, server_hostname=host) as tls:
            der = tls.getpeercert(binary_form=True)
    out = read_cert(der)
    out.update(trusted=trusted, why=why, checked=time.time())
    return out
