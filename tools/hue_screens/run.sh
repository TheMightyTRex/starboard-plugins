#!/usr/bin/env bash
# The Philips Hue plug-in's pages in Starboard, checked and pictured (20 November 2026):
#   tools/hue_screens/run.sh [starboard checkout]
# Builds the plug-in's image, runs it locked down as Starboard does (read only, no capabilities, its memory limit)
# against the made-up bridge (tests/hue_mock_bridge.py), starts Starboard's example server with the plug-in added
# (tools/hue_screens/example_server.py), and runs check.mjs in the Playwright image with axe-core. Pictures and
# check.json go to tools/hue_screens/out (not committed). Look at every picture.
set -euo pipefail
cd "$(dirname "$0")/../.."
sb="$(cd "${1:-${STARBOARD_DIR:-../starboard}}" && pwd)"
PORT="${SHOTS_PORT:-18811}" BRIDGE_PORT="${BRIDGE_PORT:-18443}" PLUGIN_PORT="${PLUGIN_PORT:-18931}"
PLAYWRIGHT="1.63.0" AXE_VERSION="4.14.0"
cache="${PLAYWRIGHT_NPM_CACHE:-/mnt/pool/build-cache/npm-playwright-1.63}"
axe_dir="${AXE_CACHE:-/mnt/pool/build-cache/npm-axe-$AXE_VERSION}"
work="$(mktemp -d -p /mnt/pool/build-cache/tmp hue-screens.XXXX)"
pids=()
trap 'kill "${pids[@]}" 2>/dev/null || true; docker rm -f hue-screens >/dev/null 2>&1 || true; rm -rf "$work"' EXIT
docker build -q -t local/philips-hue:screens philips-hue >/dev/null
mkdir -p "$work/data" "$work/run" "$work/sb" "$work/out"
chmod 755 "$work"
chmod 777 "$work/data" "$work/out"
echo '{"only_dark": true, "only_apps": []}' > "$work/run/settings.json"
echo sbk_made_up > "$work/run/key"
python3 tests/hue_mock_bridge.py "$BRIDGE_PORT" > "$work/bridge.log" 2>&1 & pids+=($!)
docker run -d --name hue-screens --network host --read-only --tmpfs /tmp:size=64m --cap-drop ALL --security-opt no-new-privileges:true \
  --user 10001:10001 --pids-limit 64 --memory 48m --cpus 0.25 -e PORT="$PLUGIN_PORT" -e HUE_DISCOVER=off -v "$work/data:/data" -v "$work/run:/run/starboard:ro" \
  local/philips-hue:screens >/dev/null
EXAMPLE_CONTAINERS=1 python3 tools/hue_screens/example_server.py "$sb" "$work/sb" "$PORT" "$PLUGIN_PORT" > "$work/server.log" 2>&1 & pids+=($!)
for _ in $(seq 1 40); do grep -q READY "$work/server.log" 2>/dev/null && break; sleep 1; done
grep -q READY "$work/server.log" || { cat "$work/server.log"; echo "The example server did not start" >&2; exit 1; }
if [ ! -f "$axe_dir/node_modules/axe-core/axe.min.js" ]; then
  mkdir -p "$axe_dir"
  docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$axe_dir:/a" -w /a "mcr.microsoft.com/playwright:v$PLAYWRIGHT-noble" \
    sh -c "npm init -y >/dev/null && npm i --silent axe-core@$AXE_VERSION >/dev/null"
fi
status=0
docker run --rm --memory 3g --memory-swap 3g --cpus 4 --network host -u "$(id -u):$(id -g)" -e HOME=/tmp \
  -e BASE="http://127.0.0.1:$PORT" -e BRIDGE="127.0.0.1:$BRIDGE_PORT" -e PASSWORD_FILE=/work/sb/password -e OUT=/work/out \
  -e AXE=/axe/node_modules/axe-core/axe.min.js -v "$work:/work" -v "$axe_dir:/axe:ro" -v "$cache:/cache:ro" \
  -v "$PWD/tools/hue_screens/check.mjs:/j/check.mjs:ro" "mcr.microsoft.com/playwright:v$PLAYWRIGHT-noble" \
  sh -c "mkdir -p /tmp/s && cp /j/check.mjs /tmp/s/ && cd /tmp/s && ln -s /cache/node_modules node_modules && node check.mjs" || status=$?
mkdir -p tools/hue_screens/out
cp "$work"/out/* tools/hue_screens/out/ 2>/dev/null || true
cp "$work"/server.log tools/hue_screens/out/server.log
docker logs hue-screens > tools/hue_screens/out/plugin.log 2>&1 || true
docker stats --no-stream --format 'Plug-in memory after the check: {{.MemUsage}}, processor {{.CPUPerc}}' hue-screens | tee tools/hue_screens/out/memory.txt
exit $status
