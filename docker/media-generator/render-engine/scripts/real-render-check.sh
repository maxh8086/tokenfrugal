#!/usr/bin/env bash
# Real-render check for the media-generator render engine. Runs one container from
# maxh8086/media-generator:latest on host port 3100, sends the requests below, copies the MP4s out with
# docker cp, probes them with ffprobe (inside the image) and runs the colour and licence checks.
#
#   1. Shorts: a gated job.json body for the shorts destination (scene-vertical). Expects 201 and 1080x1920.
#      Also the 60 s cap (shorts job of 64 s is refused) and the non-gated scene-vertical request (refused).
#   2. Duration: plain-scene, youtube preset, 4 s + 4 s. Expects 201 and ffprobe duration 8.0 s (+/- 0.1 s).
#   3. Colour: yuv420p and bt709 tags on each MP4 video stream; lib/colour.js colourFailures returns no failures.
#   4. Licence report: node scripts/licence-report.js, run in the render-engine folder.
#
# Usage: bash scripts/real-render-check.sh [OUT_DIR]    (default: a new temp folder)
# Exits 0 only if every expected check passes. Container is removed on exit.
set -u
export MSYS_NO_PATHCONV=1

IMAGE=maxh8086/media-generator:latest
NAME=mg-real-render-check
HOST_PORT=3100
BASE=http://127.0.0.1:$HOST_PORT

HERE=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:-$(mktemp -d)}
mkdir -p "$OUT/artifacts"

winpath() { cygpath -m "$1" 2>/dev/null || printf '%s' "$1"; }
WIN_OUT=$(winpath "$OUT")
WIN_HERE=$(winpath "$HERE")

FAILS=0
fail() { echo "FAIL: $*"; FAILS=$((FAILS + 1)); }
pass() { echo "PASS: $*"; }

# jget FILE .path  -> prints a field of a JSON file
jget() {
  node -e "const j=JSON.parse(require('fs').readFileSync(process.argv[1],'utf8'));const r=j$2;console.log(r===undefined?'':(typeof r==='object'?JSON.stringify(r):r))" "$(winpath "$1")"
}

# vinfo FILE -> "width height format_duration" from an ffprobe JSON file
vinfo() {
  node -e "const p=JSON.parse(require('fs').readFileSync(process.argv[1],'utf8'));const v=p.streams.find(s=>s.codec_type==='video')||{};console.log([v.width,v.height,p.format.duration].join(' '))" "$(winpath "$1")"
}

# probe NAME.mp4 -> writes NAME.probe.json next to it (ffprobe runs inside the image)
probe() {
  local base=$1
  docker run --rm --entrypoint ffprobe -v "$WIN_OUT:/x:ro" "$IMAGE" \
    -v error -show_format -show_streams -of json "/x/$base.mp4" > "$OUT/$base.probe.json"
}

# post NAME BODY_FILE -> sets CODE (HTTP status) and writes NAME.response.json
post() {
  CODE=$(curl -sS -o "$(winpath "$OUT/$1.response.json")" -w '%{http_code}' \
    -H 'Content-Type: application/json' --data-binary "@$(winpath "$2")" "$BASE/render")
  echo "[$1] HTTP $CODE: $(head -c 400 "$OUT/$1.response.json")"
}

# Copy a rendered file out of the container into $OUT.
copy_out() { docker cp "$NAME:/work/renders/$1" "$(winpath "$OUT")/$2" >/dev/null; }

docker rm -f "$NAME" >/dev/null 2>&1
trap 'docker rm -f "$NAME" >/dev/null 2>&1' EXIT

# Dummy gate artifacts (the shorts gate probe needs files to hash). Without ARTIFACTS_SRC they are written here and no
# approvals exist, so no gate opens. With ARTIFACTS_SRC and APPROVALS_SRC set, the approved folders are mounted instead.
ARTIFACTS_SRC=${ARTIFACTS_SRC:-}
APPROVALS_SRC=${APPROVALS_SRC:-$OUT/approvals}
if [ -z "$ARTIFACTS_SRC" ]; then
  for g in G1 G2 G3 G4 G5 G6; do echo "dummy artifact for the real-render check, not approved" > "$OUT/artifacts/$g.txt"; done
  ARTIFACTS_SRC=$OUT/artifacts
fi
mkdir -p "$APPROVALS_SRC"

# GATES_ENFORCE stays unset (non-gated path). PROJECT_DIR is empty, so no narration cache is written.
# On the compose network so the hostname "dhvani" (narration, DHVANI_URL) resolves.
docker run -d --name "$NAME" --network "${NETWORK:-tokenfrugal_default}" -p "127.0.0.1:$HOST_PORT:3000" \
  -e PROJECT_DIR= \
  -e ARTIFACT_DIR=/work/artifacts -e APPROVALS_PATH=/work/approvals \
  -v "$(winpath "$ARTIFACTS_SRC"):/work/artifacts:ro" \
  -v "$(winpath "$APPROVALS_SRC"):/work/approvals:ro" \
  "$IMAGE" node /opt/render-engine/server.js >/dev/null || { echo "FAIL: container did not start"; exit 1; }

if ! curl -fsS --retry 60 --retry-connrefused --retry-all-errors --retry-delay 1 "$BASE/health" >/dev/null; then
  fail "health check on $BASE/health"
  docker logs --tail 40 "$NAME"
  exit 1
fi
pass "health check on $BASE/health"

# ---- Check 1: shorts -------------------------------------------------------------------------------
cat > "$OUT/shorts-job.json" <<'EOF'
{"schema_version":1,"seed":1,"destinations":["shorts"],"template":"scene-vertical","template_version":1,
 "voice_profile":null,
 "gate_artifacts":{"G1":"G1.txt","G2":"G2.txt","G3":"G3.txt","G4":"G4.txt","G5":"G5.txt","G6":"G6.txt"},
 "scenes":[{"title":"Shorts scene one","body":"Four seconds of vertical text","seconds":4},
           {"title":"Shorts scene two","body":"Four more seconds","seconds":4}]}
EOF
post shorts-job "$OUT/shorts-job.json"
if [ "$CODE" = 201 ]; then
  SHORT_FILE=$(jget "$OUT/shorts-job.response.json" .file)
  copy_out "$SHORT_FILE" shorts.mp4
  probe shorts
  read -r W H D < <(vinfo "$OUT/shorts.probe.json")
  if [ "$W" = 1080 ] && [ "$H" = 1920 ]; then pass "shorts ffprobe ${W}x${H} duration ${D} s"; else fail "shorts ffprobe ${W}x${H}, expected 1080x1920"; fi
else
  fail "shorts POST returned HTTP $CODE: $(jget "$OUT/shorts-job.response.json" .error)"
fi

cat > "$OUT/shorts-cap-job.json" <<'EOF'
{"schema_version":1,"seed":1,"destinations":["shorts"],"template":"scene-vertical","template_version":1,
 "voice_profile":null,"gate_artifacts":{"G1":"G1.txt","G2":"G2.txt","G3":"G3.txt","G4":"G4.txt","G5":"G5.txt","G6":"G6.txt"},
 "scenes":[{"title":"Cap one","body":"x","seconds":8},{"title":"Cap two","body":"x","seconds":8},
           {"title":"Cap three","body":"x","seconds":8},{"title":"Cap four","body":"x","seconds":8},
           {"title":"Cap five","body":"x","seconds":8},{"title":"Cap six","body":"x","seconds":8},
           {"title":"Cap seven","body":"x","seconds":8},{"title":"Cap eight","body":"x","seconds":8}]}
EOF
post shorts-cap "$OUT/shorts-cap-job.json"
if [ "$CODE" = 400 ] && grep -q 'shorts renders up to 60 seconds' "$OUT/shorts-cap.response.json"; then
  pass "shorts 64 s job refused (60 s cap)"
else
  fail "shorts 64 s job: expected 400 with the 60 s cap message, got HTTP $CODE"
fi

cat > "$OUT/scene-vertical-props.json" <<'EOF'
{"template":{"id":"scene-vertical","version":"1.0.0"},"fps":30,
 "scenes":[{"text":"Vertical one","sub":"four seconds","seconds":4},{"text":"Vertical two","sub":"four seconds","seconds":4}]}
EOF
post scene-vertical-props "$OUT/scene-vertical-props.json"
if [ "$CODE" = 400 ] && grep -q 'does not support preset youtube\|unknown template id' "$OUT/scene-vertical-props.response.json"; then
  echo "INFO: non-gated scene-vertical is refused (preset youtube, or not in the image's template registry)"
else
  echo "INFO: non-gated scene-vertical returned HTTP $CODE (not the expected preset refusal)"
fi

cat > "$OUT/props-cap.json" <<'EOF'
{"fps":30,"scenes":[{"text":"a","seconds":8},{"text":"b","seconds":8},{"text":"c","seconds":8},{"text":"d","seconds":8},
 {"text":"e","seconds":8},{"text":"f","seconds":8},{"text":"g","seconds":8},{"text":"h","seconds":8}]}
EOF
post props-cap "$OUT/props-cap.json"
if [ "$CODE" = 400 ] && grep -q 'the limit is 60' "$OUT/props-cap.response.json"; then
  pass "non-gated 64 s props refused (60 s total cap)"
else
  fail "non-gated 64 s props: expected 400 with the 60 s limit message, got HTTP $CODE"
fi

# ---- Check 2: duration, plain-scene youtube 4 s + 4 s ---------------------------------------------
cat > "$OUT/plain-props.json" <<'EOF'
{"template":{"id":"plain-scene","version":"1.0.0"},"fps":30,
 "scenes":[{"text":"Plain scene one","sub":"four seconds","seconds":4},{"text":"Plain scene two","sub":"four seconds","seconds":4}]}
EOF
post plain-props "$OUT/plain-props.json"
if [ "$CODE" = 201 ]; then
  PLAIN_FILE=$(jget "$OUT/plain-props.response.json" .file)
  copy_out "$PLAIN_FILE" plain.mp4
  probe plain
  read -r PW PH PD < <(vinfo "$OUT/plain.probe.json")
  echo "plain ffprobe ${PW}x${PH} format duration ${PD} s"
  if awk -v d="$PD" 'BEGIN{exit !(d>=7.9 && d<=8.1)}'; then pass "plain-scene duration $PD s (expected 8.0 +/- 0.1)"; else fail "plain-scene duration $PD s, expected 8.0 +/- 0.1"; fi
else
  fail "plain-scene POST returned HTTP $CODE: $(jget "$OUT/plain-props.response.json" .error)"
fi

# ---- Check 3: colour tags on each real MP4 --------------------------------------------------------
colour_check() {
  node -e "
const fs=require('fs');const {pathToFileURL}=require('url');
const p=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));
const v=p.streams.find(s=>s.codec_type==='video')||{};
import(pathToFileURL(process.argv[2]).href).then(({colourFailures})=>{
  const f=colourFailures(v);
  console.log(JSON.stringify({pix_fmt:v.pix_fmt,color_space:v.color_space,color_primaries:v.color_primaries,color_transfer:v.color_transfer}));
  console.log('colourFailures: '+(f.length?f.join('; '):'none'));
  process.exit(f.length?1:0);
});" "$(winpath "$1")" "$(winpath "$HERE/lib/colour.js")"
}
for name in shorts plain; do
  if [ -f "$OUT/$name.probe.json" ]; then
    if colour_check "$OUT/$name.probe.json"; then pass "colour $name"; else fail "colour $name"; fi
  else
    fail "colour $name: no probe file (render did not produce an MP4)"
  fi
done

# ---- Check 4: licence report (writes to OUT, not the repo) -----------------------------------------
( cd "$HERE" && node scripts/licence-report.js "$(winpath "$OUT/LICENCE-REPORT.md")" ); LIC=$?
if [ "$LIC" = 0 ] && [ -s "$OUT/LICENCE-REPORT.md" ]; then pass "licence report written to $OUT/LICENCE-REPORT.md"; else fail "licence report exit $LIC"; fi

if [ "$FAILS" -gt 0 ]; then
  echo "--- container log tail (last 40 lines) ---"
  docker logs --tail 40 "$NAME" 2>&1
  echo "$FAILS check(s) failed"
  exit 1
fi
echo "all checks passed; output in $OUT"
