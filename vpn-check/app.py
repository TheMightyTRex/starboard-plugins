"""VPN check: Shows the address and country your downloads use through the VPN, and warns if it is your home address."""
import os
import time
from sbplugin import every, fetch, keep, last_error, remember, serve, setting


def check():
    started = time.monotonic()
    ip = fetch("https://ipinfo.io/json", timeout=10)
    keep("last", {"ip": ip.get("ip", ""), "country": ip.get("country", ""), "city": ip.get("city", ""),
                  "ms": round((time.monotonic() - started) * 1000), "at": time.time()})
    return {"said": f"Through the VPN: {ip.get('ip')} in {ip.get('city') or ip.get('country')}"}


def card():
    last = remember("last") or {}
    if not last:
        return {"state": "warning", "text": last_error() or "Not checked yet"}
    home = str(setting("home_address", "")).strip()
    if home and last["ip"] == home:
        return {"state": "problem", "text": f"The VPN shows your home address, {home}. Downloads are not hidden."}
    if time.time() - last["at"] > 3 * 60 * float(setting("minutes", 15)):
        return {"state": "warning", "text": f"No answer through the VPN since {time.strftime('%H:%M', time.localtime(last['at']))}. {last_error()}"}
    return {"state": "ok", "text": f"{last['ip']} in {', '.join(x for x in (last['city'], last['country']) if x)}, {last['ms']} ms"}


every(60 * float(setting("minutes", 15)), check)
serve({"/card": card, ("POST", "/check"): check}, port=int(os.environ.get("PORT", 7791)))
