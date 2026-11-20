"""The Hue bridge on the home network, and nothing else: no Hue cloud, no account.

- Bridge(address, key, fingerprint): HTTPS to the bridge's local API. CLIP v2 (/clip/v2/resource) for lights, rooms,
  zones, devices and scenes; the bridge's version 1 API (/api/<key>/...) only for schedules, rules and the daylight
  sensor, which CLIP v2 does not have. Both take the same application key.
- The bridge's certificate is its own, signed by Signify, so no public authority vouches for it. The plug-in keeps
  its SHA-256 fingerprint when it first reaches the bridge and refuses any other afterwards (trust on first use), so
  something else on the network cannot pose as the bridge once it is paired.
- pair(): the link button flow. The bridge answers error 101 until its round button is pressed, then a key.
- discover(): asks the home network for _hue._tcp by mDNS (multicast DNS). Inside Docker's own network the question
  often goes nowhere, so the bridge's address is always the dependable way.
"""
import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import struct
import time

DEVICE_TYPE = "starboard#philips-hue"  # what the Hue app lists under the bridge's connected apps
TIMEOUT = 4


class BridgeError(Exception):
    """A sentence for the person, never a stack trace."""


class LinkButton(BridgeError):
    """The bridge's link button has not been pressed yet (its error 101)."""


def clean_address(text):
    """The bridge's address as typed: an IP address or a host name, with or without https:// and a port. Anything
    else is refused in words."""
    t = str(text or "").strip()
    t = re.sub(r"^https?://", "", t, flags=re.I).split("/", 1)[0].strip()
    host, _, port = t.partition(":") if t.count(":") == 1 else (t, "", "")
    if port and not (port.isdigit() and 0 < int(port) < 65536):
        raise BridgeError("Give the bridge's address, such as 192.168.1.20")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if not re.match(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}[A-Za-z0-9])?)*$", host):
            raise BridgeError("Give the bridge's address, such as 192.168.1.20") from None
    return f"{host}:{port}" if port else host


def _context():
    # The bridge's certificate is checked by its pinned fingerprint below, not by an authority: Signify signs it with
    # its own, which no public list holds.
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # nosec B501: pinned by fingerprint in Bridge._connect
    return ctx


class Bridge:
    def __init__(self, address, key="", fingerprint="", timeout=TIMEOUT):
        self.address = clean_address(address)
        self.key = key or ""
        self.fingerprint = fingerprint or ""
        self.timeout = timeout

    # The connection ------------------------------------------------------------------------------------------
    def _connect(self):
        host, _, port = self.address.partition(":")
        conn = http.client.HTTPSConnection(host, int(port or 443), timeout=self.timeout, context=_context())
        try:
            conn.connect()
        except (OSError, ssl.SSLError):
            conn.close()
            raise BridgeError(f"The bridge at {self.address} did not answer. Check that it is on and on the same network") from None
        seen = hashlib.sha256(conn.sock.getpeercert(binary_form=True) or b"").hexdigest()
        if self.fingerprint and seen != self.fingerprint:
            conn.close()
            raise BridgeError(f"Something at {self.address} answered with a different certificate from the bridge you paired. "
                              "If you replaced the bridge, remove it on Bridge and pair the new one")
        self.seen = seen
        return conn

    def request(self, method, path, body=None):
        conn = self._connect()
        try:
            headers = {"Accept": "application/json", "User-Agent": "Starboard plug-in"}
            if self.key and path.startswith("/clip/"):
                headers["hue-application-key"] = self.key
            data = None
            if body is not None:
                data = json.dumps(body).encode()
                headers["Content-Type"] = "application/json"
            conn.request(method, path, body=data, headers=headers)
            r = conn.getresponse()
            raw = r.read(4 * 1024 * 1024)
        except (OSError, http.client.HTTPException):
            raise BridgeError(f"The bridge at {self.address} stopped answering part way. Try again") from None
        finally:
            conn.close()
        if r.status in (401, 403):
            raise BridgeError("The bridge no longer knows this plug-in. Remove the bridge on Bridge and pair it again")
        if r.status == 404 and path.startswith("/clip/"):
            raise BridgeError("This bridge does not have the newer Hue API. Update it in the Hue app, then try again")
        if r.status == 429 or r.status == 503:
            raise BridgeError("The bridge is busy. Wait a moment and try again")
        try:
            out = json.loads(raw or b"null")
        except ValueError:
            raise BridgeError(f"The bridge at {self.address} gave an answer this plug-in cannot read") from None
        if r.status >= 400:
            raise BridgeError(_first_error(out) or f"The bridge refused it (error {r.status})")
        return out

    # Before pairing ------------------------------------------------------------------------------------------
    def config(self):
        """The bridge's public details, which it gives without a key: name, bridge id, model and software."""
        out = self.request("GET", "/api/0/config")
        if not isinstance(out, dict) or not out.get("bridgeid"):
            raise BridgeError(f"What answered at {self.address} is not a Hue bridge")
        return out

    def pair(self):
        """One try. LinkButton until the button is pressed; then the key, which is kept."""
        out = self.request("POST", "/api", {"devicetype": DEVICE_TYPE, "generateclientkey": True})
        first = out[0] if isinstance(out, list) and out else {}
        if "success" in first and first["success"].get("username"):
            self.key = first["success"]["username"]
            return self.key
        err = (first.get("error") or {}) if isinstance(first, dict) else {}
        if err.get("type") == 101:
            raise LinkButton("The link button has not been pressed yet")
        raise BridgeError(err.get("description") or "The bridge did not pair")

    # CLIP v2 ------------------------------------------------------------------------------------------------
    def resources(self):
        """Every resource in one answer: lights, rooms, zones, devices, scenes, grouped lights and the rest."""
        out = self.request("GET", "/clip/v2/resource")
        if (out or {}).get("errors"):
            raise BridgeError(_first_error(out) or "The bridge gave an error")
        return out.get("data") or []

    def put(self, rtype, rid, body):
        if not re.match(r"^[a-z_]+$", rtype) or not re.match(r"^[0-9a-fA-F-]{8,64}$", str(rid)):
            raise BridgeError("That is not something on this bridge")
        out = self.request("PUT", f"/clip/v2/resource/{rtype}/{rid}", body)
        if (out or {}).get("errors"):
            raise BridgeError(_first_error(out) or "The bridge refused the change")
        return out

    # Version 1: schedules, rules and the daylight sensor ----------------------------------------------------
    def v1(self, method, path, body=None):
        if not self.key:
            raise BridgeError("Pair a bridge first, on Bridge")
        out = self.request(method, f"/api/{self.key}{path}", body)
        if isinstance(out, list) and out and isinstance(out[0], dict) and "error" in out[0]:
            raise BridgeError(_first_error(out) or "The bridge refused it")
        return out


def _first_error(out):
    if isinstance(out, dict):
        errs = out.get("errors") or []
        return str((errs[0] or {}).get("description") or "")[:200] if errs else ""
    if isinstance(out, list):
        for x in out:
            if isinstance(x, dict) and "error" in x:
                return str((x["error"] or {}).get("description") or "")[:200]
    return ""


# mDNS discovery -----------------------------------------------------------------------------------------------
MDNS = ("224.0.0.251", 5353)
SERVICE = "_hue._tcp.local"


def _question(name):
    q = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\0"
    # One question, PTR, class IN with the "answer me directly" bit, so the answer can come to this port
    return struct.pack(">HHHHHH", 0, 0, 1, 0, 0, 0) + q + struct.pack(">HH", 12, 0x8001)


def _name(packet, at, depth=0):
    labels = []
    while at < len(packet) and depth < 20:
        n = packet[at]
        if n == 0:
            return ".".join(labels), at + 1
        if n & 0xC0 == 0xC0:
            ptr = struct.unpack(">H", packet[at:at + 2])[0] & 0x3FFF
            rest, _ = _name(packet, ptr, depth + 1)
            return ".".join(labels + ([rest] if rest else [])), at + 2
        labels.append(packet[at + 1:at + 1 + n].decode("utf-8", "replace"))
        at += 1 + n
    return ".".join(labels), at


def parse_answer(packet):
    """The Hue bridges named in one mDNS answer: [(instance name, IPv4 address or "")]."""
    try:
        _, flags, qd, an, ns, ar = struct.unpack(">HHHHHH", packet[:12])
        at = 12
        for _ in range(qd):
            _, at = _name(packet, at)
            at += 4
        found, addresses = [], {}
        for _ in range(an + ns + ar):
            name, at = _name(packet, at)
            rtype, _, _, length = struct.unpack(">HHIH", packet[at:at + 10])
            at += 10
            rdata_at = at
            at += length
            if rtype == 12 and name.lower() == SERVICE:
                target, _ = _name(packet, rdata_at)
                found.append(target)
            elif rtype == 1 and length == 4:
                addresses[name.lower()] = socket.inet_ntoa(packet[rdata_at:rdata_at + 4])
        first_a = next(iter(addresses.values()), "")
        return [(t.split(".")[0], first_a) for t in found]
    except (struct.error, IndexError, OSError):
        return []


def discover(seconds=1.5):
    """Hue bridges that answer an mDNS question on the home network: [{"address", "name"}]. Empty when nothing
    answers, which inside Docker's own network is usual. HUE_DISCOVER=off asks nothing, for the pictures and tests."""
    if os.environ.get("HUE_DISCOVER") == "off":
        return []
    out = {}
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 255)
        s.settimeout(0.3)
        s.sendto(_question(SERVICE), MDNS)
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                packet, (src, _) = s.recvfrom(9000)
            except (socket.timeout, TimeoutError):
                continue
            for name, address in parse_answer(packet):
                out[address or src] = {"address": address or src, "name": name}
    except OSError:
        return []
    finally:
        s.close()
    return list(out.values())
