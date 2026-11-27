"""Single sign-on (DASH-589, stage 1): the skeleton of the sign-in provider plug-in.

This version has no provider in it yet. It holds the two settings the provider will need, and says in plain words what
state they are in: a switch that turns single sign-on on or off, and the address the provider will live at, taken from
the Tailscale name of this server (such as starboard.tail1234.ts.net).

Passkeys are tied to that address for ever: a passkey made at one address does not work at another. So the plug-in keeps the
first valid address it sees in /data/address.json, and says so in words when the setting later differs. The owner can start
again with a new address by choosing Use the new address, which asks first.

Nothing runs at rest. The container starts when Starboard asks for its card, answers from its own settings, keeps nothing
but that one small file, and rests again. It makes no network call: it never asks Tailscale, and it does not check that the
name answers.
"""
import os
import re
import time

import sbplugin as sb
from sbplugin import band, serve, setting

LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
# A MagicDNS name is a machine, then the tailnet, then ts.net: starboard.tail1234.ts.net or starboard.example-fox.ts.net.
TAILSCALE_NAME = re.compile(rf"^{LABEL}\.{LABEL}\.ts\.net$")
EXAMPLE = "starboard.tail1234.ts.net"


def check_name(raw):
    """(name, problem): the Tailscale name in the form the provider will use, or what is wrong with it in words."""
    text = str(raw or "").strip().lower()
    if not text:
        return "", "Enter the Tailscale name of this server, such as " + EXAMPLE + "."
    for prefix in ("https://", "http://"):
        if text.startswith(prefix):
            text = text[len(prefix):]
    text = text.rstrip("/").rstrip(".")  # a trailing dot is how Tailscale writes the name in its status output
    if re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{1,3}){3}(?::[0-9]+)?", text) or re.fullmatch(r"[0-9a-f:]{2,}", text):
        return "", "That is an address, not a name. Use the name that ends in .ts.net, not the 100. address."
    if any(c in text for c in "/?#@ ") or re.search(r":\d+$", text):
        return "", "Enter only the name, with no port, path or spaces. The provider uses the https address on port 443."
    if not text.endswith(".ts.net"):
        return "", "A Tailscale name ends in .ts.net, such as " + EXAMPLE + ". Find yours in Tailscale's admin page, under Machines."
    if not TAILSCALE_NAME.match(text):
        return "", "That is not a full Tailscale name. A full name has the machine, the tailnet and .ts.net, such as " + EXAMPLE + "."
    return text, ""


def kept():
    """The address kept the first time a valid one was seen: {"name", "set"} or None."""
    got = sb.remember("address", None)
    return got if isinstance(got, dict) and got.get("name") else None


def state():
    """The plug-in's whole state, worked out from its settings and the one kept file."""
    on = bool(setting("enabled", False))
    name, problem = check_name(setting("tailscale_name", ""))
    first = kept()
    if not on:
        return {"state": "off", "on": False, "name": name, "kept": first["name"] if first else "", "problem": ""}
    if problem:
        return {"state": "needs-name", "on": True, "name": "", "kept": first["name"] if first else "", "problem": problem}
    if first and first["name"] != name:
        return {"state": "changed", "on": True, "name": name, "kept": first["name"], "problem": ""}
    if not first:
        sb.keep("address", {"name": name, "set": int(time.time())})
    return {"state": "waiting", "on": True, "name": name, "kept": name, "problem": ""}


def card():
    s = state()
    if s["state"] == "off":
        return band({"state": "ok", "text": "Single sign-on is off. Nothing runs for it and nothing is asked of Tailscale."}, "inactive", label="Off")
    if s["state"] == "needs-name":
        return band({"state": "warning", "text": s["problem"]}, "needs_setup", label="Needs a name")
    if s["state"] == "changed":
        return band({"state": "warning", "text": f"The name is now {s['name']}, but the provider keeps {s['kept']}. Passkeys made at one address do not work at "
                                                 "another. Change the name back, or choose Use the new address and make passkeys again."[:300]},
                    "warning", label="Name changed")
    return band({"state": "ok", "text": f"The provider will live at https://{s['name']}. Passkeys will be tied to this address. "
                                        "The provider is not in this version yet."}, "waiting", label="Waiting for provider")


def use_new_address():
    """Forget the kept address so the next check keeps the one now in the settings. No provider exists yet, so no passkey is lost."""
    s = state()
    if s["state"] != "changed":
        return {"said": "There is nothing to change. The name in the settings is the one kept."}
    sb.keep("address", {"name": s["name"], "set": int(time.time())})
    return {"said": f"Now using {s['name']}. Passkeys made at {s['kept']} do not work here."}


def check():
    s = state()
    words = {"off": "Single sign-on is off.", "needs-name": s["problem"],
             "changed": f"The name is {s['name']} but {s['kept']} is kept. Passkeys are tied to the kept name.",
             "waiting": f"https://{s['name']} will be the provider's address."}[s["state"]]
    return {"said": words}


ROUTES = {"/card": card, ("POST", "/check"): check, ("POST", "/use-new-address"): use_new_address}

if __name__ == "__main__":
    serve(ROUTES, port=int(os.environ.get("PORT", 8080)))
