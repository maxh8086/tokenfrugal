#!/bin/sh
# Renders golden-candidate stills for shader items with the pipeline's `hyperframes snapshot` path and
# probes each composition in headless Chrome for console errors and window.__hf.buildReady.shaders.
# Runs inside the media-generator image (see check_golden.py, which mounts the inputs).
#   /src      catalogue (read only)
#   /scripts  this folder (read only)
#   /out      output root; frames land in /out/<subdir>/<item>/
# Usage: render_items.sh <subdir> <item> [item ...]
set -u
SUB="$1"; shift
FAILS=0
for item in "$@"; do
  rm -rf /tmp/proj && mkdir -p /tmp/proj
  if ! cp -r "/src/$item/compositions/." /tmp/proj/; then
    echo "FAIL copy $item"; FAILS=$((FAILS+1)); continue
  fi
  cp "/tmp/proj/$item.html" /tmp/proj/index.html
  dest="/out/$SUB/$item"
  rm -rf "$dest" && mkdir -p "$dest"
  if hyperframes snapshot --at 0.5,1 --no-end -o "$dest" /tmp/proj > "$dest/snapshot.log" 2>&1; then
    snap="ok"
  else
    snap="failed"; FAILS=$((FAILS+1))
  fi
  NODE_PATH=/usr/local/lib/node_modules/hyperframes/node_modules node /scripts/console_probe.js /tmp/proj/index.html > "$dest/console.json" 2> "$dest/probe.err" || true
  echo "$item snapshot=$snap frames=$(ls "$dest" | grep -c '\.png') probe=$(tr -d '\n' < "$dest/console.json" | cut -c1-200)"
done
echo "DONE failures=$FAILS"
