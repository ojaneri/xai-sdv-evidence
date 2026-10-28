#!/usr/bin/env bash
# Run the cost bench on a remote ARM host and bring the results back.
#
# The cost model T = N * t_pass(N) claims that an engineer can measure t_pass
# on their own hardware, count the passes, and predict the runtime without
# repeating this bench. A second instruction set tests that claim: the pass
# counts must come back identical (a property of the method) while the
# milliseconds differ (a property of the machine), and the model must predict
# the new milliseconds from the t_pass measured there.
#
# Use a host with dedicated cores (e.g. AWS c7g, Neoverse-V1). Burstable
# instances (t4g) throttle under sustained load and their timings are not
# usable; their pass counts still are. A Graviton is a server-class part, not
# automotive silicon.
#
# Usage:
#   ./src/cost/run_on_arm.sh ubuntu@<ip> ~/.ssh/<key>.pem
#
# Requires on the remote: Ubuntu 22.04/24.04 arm64, ~20 GB disk, python3.
set -euo pipefail

HOST="${1:?usage: $0 user@host /path/to/key.pem}"
KEY="${2:?usage: $0 user@host /path/to/key.pem}"
SSH="ssh -i $KEY -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20"
SCP="scp -i $KEY -o StrictHostKeyChecking=accept-new"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$REPO/results/cost/arm-$STAMP"

echo "== 1/5 remote architecture =="
$SSH "$HOST" 'uname -m; nproc; grep -m1 "^model name\|^Model" /proc/cpuinfo || true; free -g | sed -n 2p'

echo "== 2/5 shipping the code (no data, no venv) =="
$SSH "$HOST" 'rm -rf ~/xai-bench && mkdir -p ~/xai-bench/src/cost ~/xai-bench/results/cost'
$SCP -q "$REPO"/requirements.txt "$HOST":~/xai-bench/
$SCP -q "$REPO"/src/common.py "$HOST":~/xai-bench/src/
$SCP -q "$REPO"/src/cost/*.py "$HOST":~/xai-bench/src/cost/

echo "== 3/5 installing (the slow part: torch) =="
$SSH "$HOST" 'cd ~/xai-bench && \
  sudo apt-get update -qq && sudo apt-get install -y -qq python3-venv >/dev/null && \
  python3 -m venv .venv && \
  .venv/bin/pip install -q --upgrade pip && \
  .venv/bin/pip install -q -r requirements.txt && \
  .venv/bin/python -c "import shap, lime, captum, xgboost, torch; print(\"imports ok\")"'

echo "== 4/5 running the cost bench =="
# Only the cost scripts: they need no dataset. setsid + nohup keep the run
# alive if the ssh connection drops.
$SSH "$HOST" 'cd ~/xai-bench && export PYTHONPATH=src && \
  setsid nohup .venv/bin/python -u -m cost.xai_cost --repeats 40 --kernel-repeats 3 \
      --out results/cost/tabular_arm.json > results/cost/cost_arm.log 2>&1 < /dev/null & \
  echo started'
echo "  waiting for the cost bench..."
until $SSH "$HOST" 'test -f ~/xai-bench/results/cost/tabular_arm.json' 2>/dev/null; do sleep 20; done
$SSH "$HOST" 'cd ~/xai-bench && export PYTHONPATH=src && \
  setsid nohup .venv/bin/python -u -m cost.validate_model > results/cost/validate_arm.log 2>&1 < /dev/null & \
  echo started'
echo "  waiting for the model validation (this one is long)..."
until $SSH "$HOST" 'grep -q "model_validation.json\|Traceback" ~/xai-bench/results/cost/validate_arm.log' 2>/dev/null; do sleep 30; done
$SSH "$HOST" 'cat ~/xai-bench/results/cost/validate_arm.log'

echo "== 5/5 bringing results back =="
mkdir -p "$OUT"
$SCP -q "$HOST":'~/xai-bench/results/cost/*' "$OUT"/ || true
echo "-> $OUT"
ls -la "$OUT"
echo "Compare: pass counts must equal those of results/cost/tabular_canonical.json;"
echo "the milliseconds will not."
