"""VPN check: Shows the address and country your downloads use through the VPN, and warns if it is your home address."""
import os
import time
from sbplugin import band, every, fetch, keep, last_error, remember, serve, setting


def check():
    started = time.monotonic()
    ip = fetch("https://ipinfo.io/json", timeout=10)
    keep("last", {"ip": ip.get("ip", ""), "country": ip.get("country", ""), "city": ip.get("city", ""),
                  "ms": round((time.monotonic() - started) * 1000), "at": time.time()})
    return {"said": f"Through the VPN: {ip.get('ip')} in {ip.get('city') or ip.get('country')}"}


def card():
    last = remember("last") or {}
    if not last:
        err = last_error()
        return band({"state": "warning", "text": err or "Not checked yet"}, "problem" if err else "waiting", label=None if err else "Checking soon")
    home = str(setting("home_address", "")).strip()
    if home and last["ip"] == home:
        return band({"state": "problem", "text": f"The VPN shows your home address, {home}. Downloads are not hidden."},
                    "problem", last["at"], "Home address showing")
    if time.time() - last["at"] > 3 * 60 * float(setting("minutes", 15)):
        return band({"state": "warning", "text": f"No answer through the VPN since {time.strftime('%H:%M', time.localtime(last['at']))}. {last_error()}"},
                    "warning", last["at"], "No answer")
    return band({"state": "ok", "text": f"{last['ip']} in {', '.join(x for x in (last['city'], last['country']) if x)}, {last['ms']} ms"},
                "protected", last["at"])


every(60 * float(setting("minutes", 15)), check)
serve({"/card": card, ("POST", "/check"): check}, port=int(os.environ.get("PORT", 7791)))
