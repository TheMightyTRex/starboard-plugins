"""Home Assistant: Your house in one sentence on the dashboard: the things you choose from Home Assistant."""
from sbplugin import fetch, serve, setting


def card():
    base, token = str(setting("address", "")).rstrip("/"), setting("token", "")
    ids = setting("entities", []) or []
    if not base or not token or not ids:
        return {"state": "warning", "text": "Add the address, a token and what to show in the plug-in's settings"}
    alert = {s.strip().lower() for s in str(setting("alert_on", "on, open, unlocked")).split(",") if s.strip()}
    parts, warn = [], False
    for eid in ids[:8]:
        s = fetch(f"{base}/api/states/{eid}", {"Authorization": f"Bearer {token}"})
        name = (s.get("attributes") or {}).get("friendly_name") or eid
        unit = (s.get("attributes") or {}).get("unit_of_measurement") or ""
        state = s.get("state", "")
        warn |= state.lower() in alert
        parts.append(f"{name}: {state}{' ' + unit if unit else ''}")
    return {"state": "warning" if warn else "ok", "text": ". ".join(parts)}


serve({"/card": card})
