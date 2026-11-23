#!/usr/bin/env bash
# The break grids' page, checked and pictured (23 November 2026, DASH-537): tools/tv_break_screens/run.sh
# Starts the plug-in's own web server on made-up data (demo_server.py) and runs check.mjs in the Playwright image with
# axe-core. Writes tools/tv_break_screens/out/check.json and pictures (not committed). Look at every picture.
set -euo pipefail
cd "$(dirname "$0")/../.."
PORT="${PORT:-18940}" PLAYWRIGHT="1.63.0" AXE_VERSION="4.14.0"
cache="${PLAYWRIGHT_NPM_CACHE:-/mnt/pool/build-cache/npm-playwright-1.63}"
axe_dir="${AXE_CACHE:-/mnt/pool/build-cache/npm-axe-$AXE_VERSION}"
work="$(mktemp -d -p /mnt/pool/build-cache/tmp tv-breaks.XXXX)"
trap 'kill "$server" 2>/dev/null || true; rm -rf "$work"' EXIT
chmod 777 "$work"
python3 tools/tv_break_screens/demo_server.py "$PORT" "$work/data" > "$work/server.log" 2>&1 &
server=$!
for _ in $(seq 1 20); do grep -q READY "$work/server.log" 2>/dev/null && break; sleep 1; done
grep -q READY "$work/server.log" || { cat "$work/server.log"; echo "The demo server did not start" >&2; exit 1; }
url="$(head -1 "$work/server.log")"
mkdir -p "$work/out"; chmod 777 "$work/out"
status=0
docker run --rm --memory 3g --memory-swap 3g --cpus 4 --network host -u "$(id -u):$(id -g)" -e HOME=/tmp -e URL="$url" -e OUT=/work/out \
  -e AXE=/axe/node_modules/axe-core/axe.min.js -v "$work:/work" -v "$axe_dir:/axe:ro" -v "$cache:/cache:ro" \
  -v "$PWD/tools/tv_break_screens/check.mjs:/j/check.mjs:ro" "mcr.microsoft.com/playwright:v$PLAYWRIGHT-noble" \
  sh -c "mkdir -p /tmp/s && cp /j/check.mjs /tmp/s/ && cd /tmp/s && ln -s /cache/node_modules node_modules && node check.mjs" || status=$?
mkdir -p tools/tv_break_screens/out
cp "$work"/out/* tools/tv_break_screens/out/ 2>/dev/null || true
exit $status
