"""Ad blocking: How many adverts and trackers Pi-hole or AdGuard Home blocked today."""
import base64
from sbplugin import fetch, serve, setting


def card():
    base = str(setting("address", "")).rstrip("/")
    if not base:
        raise ValueError("Add the address in the plug-in's settings")
    if setting("kind", "Pi-hole") == "AdGuard Home":
        auth = base64.b64encode(f"{setting('username', '')}:{setting('password', '')}".encode()).decode()
        s = fetch(f"{base}/control/stats", {"Authorization": f"Basic {auth}"})
        blocked, total = int(s.get("num_blocked_filtering") or 0), int(s.get("num_dns_queries") or 0)
    else:  # Pi-hole 6: a session for this one question, then signed out
        sid = (fetch(f"{base}/api/auth", data={"password": setting("password", "")}).get("session") or {}).get("sid")
        try:
            q = (fetch(f"{base}/api/stats/summary", {"X-FTL-SID": sid or ""}).get("queries") or {})
        finally:
            if sid:
                fetch(f"{base}/api/auth", {"X-FTL-SID": sid}, method="DELETE", raw=True)
        blocked, total = int(q.get("blocked") or 0), int(q.get("total") or 0)
    share = f"{round(100 * blocked / total)}% of {total:,} lookups" if total else "no lookups yet"
    return {"value": blocked, "label": "blocked", "note": share}


serve({"/card": card})
