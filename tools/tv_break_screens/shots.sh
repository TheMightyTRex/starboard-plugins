#!/usr/bin/env bash
# Takes the break grids' help pictures into help/images/tv-station (23 November 2026): tools/tv_break_screens/shots.sh [starboard checkout]
set -euo pipefail
cd "$(dirname "$0")/../.."
sb="$(cd "${1:-${STARBOARD_DIR:-../starboard}}" && pwd)"
PORT="${PORT:-18942}" cache="${PLAYWRIGHT_NPM_CACHE:-/mnt/pool/build-cache/npm-playwright-1.63}"
work="$(mktemp -d -p /mnt/pool/build-cache/tmp tv-breaks-shots.XXXX)"
trap 'kill "$server" 2>/dev/null || true; rm -rf "$work"' EXIT
chmod 777 "$work"
python3 tools/tv_break_screens/demo_server.py "$PORT" "$work/data" > "$work/server.log" 2>&1 &
server=$!
for _ in $(seq 1 20); do grep -q READY "$work/server.log" 2>/dev/null && break; sleep 1; done
mkdir -p "$work/out"; chmod 777 "$work/out"
docker run --rm --network host -u "$(id -u):$(id -g)" -e HOME=/tmp -e URL="$(head -1 "$work/server.log")" -e OUT=/work/out -e ANNOTATE=/j/annotate.js \
  -v "$work:/work" -v "$cache:/cache:ro" -v "$PWD/tools/tv_break_screens/${SHOTS:-shots}.mjs:/j/shots.mjs:ro" -v "$sb/tools/screenshots/annotate.js:/j/annotate.js:ro" \
  mcr.microsoft.com/playwright:v1.63.0-noble sh -c "mkdir -p /tmp/s && cp /j/shots.mjs /tmp/s/ && cd /tmp/s && ln -s /cache/node_modules node_modules && node shots.mjs"
mkdir -p tools/tv_break_screens/out && cp "$work"/out/*.png tools/tv_break_screens/out/
