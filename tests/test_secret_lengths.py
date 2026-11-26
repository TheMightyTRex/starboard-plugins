"""Keys the apps sign with must be long enough (26 November 2026). Starboard makes each {secret:name} 48 characters
(384 bits), and Kavita signs its sign-in tokens with HMAC-SHA512, which refuses a key under 64 bytes: the first account
could not be made ("400 Error, Something went wrong when registering user", IDX10720). Kavita now joins three secrets."""
import json
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import ROOT, manifest  # noqa: E402

SECRET_LENGTH = 48  # characters Starboard makes for one secret (secrets.token_hex(24))
HOLE = re.compile(r"\{secret:[a-z][a-z0-9_]{0,29}\}")
KEYLIKE = re.compile(r"(jwt|token_?key|signing|session_?secret|secret_?key|encryption)", re.I)


def ids():
    return sorted(d for d in os.listdir(ROOT) if os.path.isfile(os.path.join(ROOT, d, "starboard-plugin.json")))


def key_values(m):
    """(where, value) for every env value and file with a key-like name or content in a container."""
    for c in m.get("containers") or []:
        for k, v in (c.get("env") or {}).items():
            if KEYLIKE.search(k) and "{secret:" in str(v):
                yield f"{c['name']} env {k}", str(v)
        for fname, text in (c.get("files") or {}).items():
            for line in str(text).splitlines():
                if KEYLIKE.search(line.split(":")[0]) and "{secret:" in line:
                    yield f"{c['name']} file {fname}", line.split(":", 1)[1]


def length(value):
    """Characters of the value once each secret is filled, and nothing else counted."""
    return len(HOLE.findall(value)) * SECRET_LENGTH


class SecretLengths(unittest.TestCase):
    def test_kavitas_token_key_is_long_enough_for_hmac_sha512(self):
        m = manifest("kavita")
        text = m["containers"][0]["files"]["appsettings.json"]
        key = json.loads(re.sub(r"\{secret:[a-z0-9_]+\}", lambda h: "x" * SECRET_LENGTH, text))["TokenKey"]
        self.assertGreaterEqual(len(key), 64, "TokenKey under 64 characters: Kavita cannot make the first account")
        self.assertGreaterEqual(len(key), 128)
        names = HOLE.findall(text)
        self.assertEqual(len(names), len(set(names)), "each secret may be used once, or the key repeats")
        self.assertEqual(names[0], "{secret:token_key}", "the first part keeps the secret an old install already has")

    def test_every_key_like_secret_is_at_least_256_bits(self):
        seen = 0
        for pid in ids():
            for where, value in key_values(manifest(pid)):
                seen += 1
                self.assertGreaterEqual(length(value), 32, f"{pid} {where}")
        self.assertGreater(seen, 1)


if __name__ == "__main__":
    unittest.main()
