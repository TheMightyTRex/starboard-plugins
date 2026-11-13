#!/bin/sh
# Builds the examples' shared image locally, tagged as the manifests name it before it is pinned. Nothing is pushed.
set -e
cd "$(dirname "$0")/.."
v=$(python3 -c "import sys;sys.path.insert(0,'tools');import examples_src;print(examples_src.IMAGE_VERSION)")
docker build -q -t "ghcr.io/themightytrex/starboard-plugin-examples:$v" . >/dev/null && echo "built ghcr.io/themightytrex/starboard-plugin-examples:$v"
