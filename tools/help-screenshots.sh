#!/usr/bin/env bash
# Takes the plug-ins' help pictures listed in tools/help_screenshots/shots.json (help/images/<plug-in>) from Starboard's
# example server, marked up with Starboard's help_shoot.mjs and annotate.js (red outline, curved arrow, step badge):
#   tools/help-screenshots.sh [starboard checkout]      (default: STARBOARD_DIR, then ../starboard)
# Each shot names its plug-in (library-cleanup when it names none). The example server is Starboard's, with this
# collection's catalogue.json and the plug-in's real manifest (tools/help_screenshots/example_server.py).
# SHOTS_PORT picks the port (18810). Look at every picture before committing.
set -euo pipefail
cd "$(dirname "$0")/.."
sb="$(cd "${1:-${STARBOARD_DIR:-../starboard}}" && pwd)"
PORT="${SHOTS_PORT:-18810}"
PLAYWRIGHT="1.63.0"
cache="${PLAYWRIGHT_NPM_CACHE:-/mnt/pool/build-cache/npm-playwright-1.63}"
[ -d "$cache/node_modules/playwright" ] || cache=""
work="$(mktemp -d)"
server=""
trap 'kill "$server" 2>/dev/null || true; rm -rf "$work"' EXIT
status=0
plugins="$(python3 -c "import json; print(' '.join(sorted({s.get('plugin', 'library-cleanup') for s in json.load(open('tools/help_screenshots/shots.json'))['shots']})))")"
for plugin in $plugins; do
for phase in absent present; do
  python3 -c "import json,sys; d=json.load(open('tools/help_screenshots/shots.json')); d['shots']=[s for s in d['shots'] if s['phase']==sys.argv[1] and s.get('plugin', 'library-cleanup')==sys.argv[3]]; json.dump(d,open(sys.argv[2],'w')); sys.exit(0 if d['shots'] else 3)" \
    "$phase" "$work/help_shots.json" "$plugin" || continue
  rm -rf "$work/data" "$work/out"
  mkdir -p "$work/out" "help/images/$plugin"
  EXAMPLE_CONTAINERS=1 python3 tools/help_screenshots/example_server.py "$sb" "$work/data" "$PORT" "$phase" "$plugin" > "$work/server.log" 2>&1 &
  server=$!
  for _ in $(seq 1 30); do grep -q READY "$work/server.log" 2>/dev/null && break; sleep 1; done
  grep -q READY "$work/server.log" || { cat "$work/server.log"; echo "The example server did not start" >&2; exit 1; }
  docker run --rm --memory 3g --memory-swap 3g --cpus 4 --network host -u "$(id -u):$(id -g)" -e HOME=/tmp \
    -e BASE="http://127.0.0.1:$PORT" -e PASSWORD_FILE=/work/data/password -e OUT=/work/out \
    -v "$work:/work" -v "$sb/tools/screenshots:/shots:ro" \
    ${cache:+-v "$cache:/cache:ro"} "mcr.microsoft.com/playwright:v$PLAYWRIGHT-noble" \
    sh -c "mkdir -p /tmp/s && cp -r /shots/help_shoot.mjs /shots/annotate.js /tmp/s/ && cp /work/help_shots.json /tmp/s/ && cd /tmp/s && if [ -d /cache/node_modules/playwright ]; then ln -s /cache/node_modules node_modules; else npm init -y >/dev/null && npm i --silent playwright@$PLAYWRIGHT >/dev/null; fi && node help_shoot.mjs" || status=$?
  kill "$server" 2>/dev/null || true
  wait "$server" 2>/dev/null || true
  server=""
  { command -v pngquant >/dev/null && pngquant --force --ext .png --quality 70-90 "$work"/out/*.png; } 2>/dev/null || true
  cp "$work"/out/*.png "help/images/$plugin/" 2>/dev/null || true
done
done
echo "Written to help/images/<plug-in>. Look at each one before committing."
exit $status
