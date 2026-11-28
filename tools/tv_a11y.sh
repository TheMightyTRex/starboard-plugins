#!/usr/bin/env bash
# Accessibility check of the TV channel plug-in's own pages, against made-up data: tools/tv_a11y.sh
# Starts tools/tv_a11y/serve.py (the real app.py, a made-up Jellyfin) and runs tools/tv_a11y/pages.mjs in the Playwright image with axe-core.
# Desktop only: 1280 and 1024 wide, light, dark and forced colours (High contrast). Run it through /mnt/pool/build-cache/heavy-run-wt2.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT="${TV_A11Y_PORT:-18797}"
work="$(mktemp -d)"
trap 'kill "$server" 2>/dev/null || true; rm -rf "$work"' EXIT
python3 tools/tv_a11y/serve.py "$PORT" "$work/data" > "$work/server.log" 2>&1 &
server=$!
for _ in $(seq 1 30); do grep -q READY "$work/server.log" 2>/dev/null && break; sleep 1; done
grep -q READY "$work/server.log" || { cat "$work/server.log"; echo "The made-up plug-in did not start" >&2; exit 1; }
TOKEN="$(grep '^token ' "$work/server.log" | cut -d' ' -f2)"
docker run --rm --memory 3g --memory-swap 3g --cpus 2 --network host -u "$(id -u):$(id -g)" -e HOME=/tmp -e BASE="http://127.0.0.1:$PORT" -e TOKEN="$TOKEN" \
  -e AXE=/tmp/a/node_modules/axe-core/axe.min.js -v "$PWD/tools/tv_a11y/pages.mjs:/j/pages.mjs:ro" \
  "mcr.microsoft.com/playwright:v1.63.0-noble" \
  sh -c "mkdir -p /tmp/a && cp /j/pages.mjs /tmp/a/ && cd /tmp/a && npm init -y >/dev/null && npm i --silent playwright@1.63.0 axe-core@4.14.0 >/dev/null 2>&1 && node pages.mjs"
