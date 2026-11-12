#!/bin/sh
# Builds each example plug-in's image locally, tagged as its manifest names it. Nothing is pushed.
set -e
cd "$(dirname "$0")/.."
for d in */Dockerfile; do
  pid=${d%/Dockerfile}
  img=$(python3 -c "import json;print(json.load(open('$pid/starboard-plugin.json'))['containers'][0]['image'])")
  docker build -q -t "$img" "$pid" >/dev/null && echo "built $img"
done
