#!/usr/bin/env bash
# Run the XAI firmware on one FIT IoT-LAB st-iotnode (STM32L475, Saclay) and
# capture its serial console until the firmware's '#' end marker.
#
# The console is attached first and the node reset afterwards, so the log
# starts at boot; the experiment is stopped as soon as '#' arrives.
# Submit the .elf: the run of record (experiment 450900) used it, while a
# .hex derived from it failed to deploy. Open only one serial connection per
# node; a second one is refused.
#
# Needs the iotlab-cli tools (pip install iotlabcli) authenticated with
# `iotlab-auth`, and an SSH key registered with FIT IoT-LAB.
#
#   IOTLAB_USER=<login> ./src/mcu/iotlab_run.sh [duration_min] [name] [node_id]
set -euo pipefail
DUR="${1:-40}"
NAME="${2:-xai-st-iotnode-r1}"
NODE_ID="${3:-1}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
BIN="${IOTLAB_BIN:-$(dirname "$(command -v iotlab-experiment)")}"
FW="${FW:-$REPO/firmware/xai_st-iotnode.elf}"
OUT="$REPO/results/mcu/$NAME"
KEY="${IOTLAB_KEY:-$HOME/.ssh/iotlab_ed25519}"
IOTLAB_USER="${IOTLAB_USER:?set IOTLAB_USER to your FIT IoT-LAB login}"
mkdir -p "$OUT"

SUB=$("$BIN/iotlab-experiment" submit -n "$NAME" -d "$DUR" \
      -l "saclay,st-iotnode,$NODE_ID,$FW")
ID=$(echo "$SUB" | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
echo "experiment $ID"
"$BIN/iotlab-experiment" wait -i "$ID" --state Running --timeout 1800
NODE="st-iotnode-$NODE_ID"
echo "node $NODE"
DEPLOY=$("$BIN/iotlab-experiment" get -i "$ID" -d)
echo "deployment $DEPLOY"
if ! echo "$DEPLOY" | python3 -c 'import sys,json; sys.exit(0 if "0" in json.load(sys.stdin) else 1)'; then
  echo "firmware deployment failed"; "$BIN/iotlab-experiment" stop -i "$ID" >/dev/null 2>&1 || true; exit 1
fi
cat > "$OUT/experiment.json" <<JSON
{"experiment_id": $ID, "site": "saclay", "node": "$NODE", "archi": "st-iotnode",
 "mcu": "STM32L475VG @ 16 MHz (CLOCK_BENCHMARK)", "duration_min": $DUR,
 "firmware": "$(basename "$FW")", "firmware_sha256": "$(sha256sum "$FW" | cut -d' ' -f1)",
 "submitted_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"}
JSON

# console first, then reset, so the capture starts at boot
( timeout $(( DUR * 60 - 60 )) ssh -i "$KEY" -o StrictHostKeyChecking=no -o ConnectTimeout=15 \
    "$IOTLAB_USER"@saclay.iot-lab.info "for i in \$(seq 40); do nc $NODE 20000 && break; sleep 5; done" \
    > "$OUT/raw_console.log" 2>"$OUT/ssh.err" ) &
CAP=$!
sleep 45
"$BIN/iotlab-node" --reset -i "$ID" > "$OUT/reset.json" 2>&1 || true
while kill -0 $CAP 2>/dev/null; do
  if grep -q '^#' "$OUT/raw_console.log" 2>/dev/null; then kill $CAP 2>/dev/null || true; break; fi
  sleep 20
done
wait $CAP 2>/dev/null || true
"$BIN/iotlab-experiment" stop -i "$ID" > /dev/null 2>&1 || true
sha256sum "$OUT/raw_console.log" > "$OUT/manifest.sha256"
echo "lines: $(wc -l < "$OUT/raw_console.log")  end-marker: $(grep -c '^#' "$OUT/raw_console.log" || true)"
