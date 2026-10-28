# Reproduction targets. Run `make help` for the list.
#
# Tier 1 (minutes, no dataset):  make smoke tables verify
# Tier 2 (hours, public data):   make data && make tier2
# Tier 3 (optional, hardware):   make mcu-host mcu-analyze, then the lab targets

PY ?= python3
export PYTHONPATH := $(CURDIR)/src
CC ?= gcc
BUILD := build

.PHONY: help smoke tables verify tier1 data data-road data-hcrl \
        cost-tabular cost-vision cost-vision-n400 cost-gradcam cost-model \
        cost-ig bus-budget tier2-cost \
        can-labels can-ids can-drift can-collapse can-sanity can-blindness \
        can-cross-vehicle can-cross-family can-drift-metrics can-ota tier2-can tier2 \
        mcu-export mcu-host mcu-analyze mcu-iotlab mcu-shepherd clean

help:
	@echo "Tier 1  smoke | tables | verify | tier1"
	@echo "Data    data-road | data-hcrl | data"
	@echo "Tier 2  cost-tabular cost-vision cost-vision-n400 cost-gradcam cost-model"
	@echo "        cost-ig bus-budget | tier2-cost"
	@echo "        can-labels can-ids can-drift can-collapse can-sanity can-blindness"
	@echo "        can-cross-vehicle can-cross-family can-drift-metrics can-ota | tier2-can"
	@echo "        tier2 (= tier2-cost tier2-can)"
	@echo "Tier 3  mcu-export mcu-host mcu-analyze | mcu-iotlab mcu-shepherd"

# ---------------------------------------------------------------- tier 1
smoke:
	$(PY) src/smoke_test.py

tables:
	$(PY) -m report.tables

verify:
	$(PY) -m report.check_paper

tier1: smoke tables verify

# ---------------------------------------------------------------- data
data-road:
	$(PY) -m can_ids.download_road

data-hcrl:
	$(PY) -m can_ids.download_hcrl

data: data-road data-hcrl

# ---------------------------------------------------------------- tier 2: cost
# Four runs of the tabular bench, combined into tabular_canonical.json.
cost-tabular:
	mkdir -p results/cost/runs
	for i in 1 2 3 4; do $(PY) -m cost.xai_cost --out results/cost/runs/tabular_run$$i.json || exit 1; done
	$(PY) -m cost.aggregate_runs results/cost/runs/tabular_run1.json results/cost/runs/tabular_run2.json \
	    results/cost/runs/tabular_run3.json results/cost/runs/tabular_run4.json

cost-vision:
	$(PY) -m cost.xai_cost_vision --out results/cost/vision.json

cost-vision-n400:
	$(PY) -m cost.xai_cost_vision --repeats 400 --out results/cost/vision_n400.json

cost-gradcam:
	$(PY) -m cost.gradcam_boundary

cost-model:
	$(PY) -m cost.validate_model

cost-ig:
	$(PY) -m cost.ig_overhead

# needs data/road/ambient and data/hcrl/normal_run_data
bus-budget:
	$(PY) -m cost.bus_budget

tier2-cost: cost-tabular cost-vision cost-vision-n400 cost-gradcam cost-model cost-ig bus-budget

# ---------------------------------------------------------------- tier 2: CAN
can-labels:
	$(PY) -m can_ids.label_stats

can-ids:
	$(PY) -m can_ids.id_overlap

can-drift:
	$(PY) -m can_ids.drift_experiment

can-collapse:
	$(PY) -m can_ids.collapse_full

can-sanity:
	$(PY) -m can_ids.sanity_masq

# reads results/can/drift.json
can-blindness:
	$(PY) -m can_ids.blindness_check

can-cross-vehicle:
	$(PY) -m can_ids.cross_vehicle 2>&1 | tee results/can/cross_vehicle.log

can-cross-family:
	$(PY) -m can_ids.cross_family

can-drift-metrics:
	$(PY) -m can_ids.drift_metrics
	$(PY) -m can_ids.drift_metrics ambient

can-ota:
	$(PY) -m can_ids.ota_drift

tier2-can: can-labels can-ids can-drift can-collapse can-sanity can-blindness can-cross-vehicle \
           can-cross-family can-drift-metrics can-ota

tier2: tier2-cost tier2-can

# ---------------------------------------------------------------- tier 3: MCU
# Rebuild the C model from the Python model and check the C port on the host.
mcu-export:
	$(PY) -m mcu.export_model

mcu-host: mcu-export
	mkdir -p $(BUILD)
	$(CC) -O2 -o $(BUILD)/host_check src/mcu/host_check.c src/mcu/xai_core.c -lm
	$(BUILD)/host_check > $(BUILD)/host_out.json
	$(PY) -m mcu.check_host $(BUILD)/host_out.json

# Re-analyse the saved console logs of the two STM32L4 boards into build/.
# (The nRF52840 analysis needs the 439 MB Shepherd HDF5 trace, not included.)
mcu-analyze:
	mkdir -p $(BUILD)/mcu
	$(PY) -m mcu.analyze results/mcu/xai-st-iotnode-r1/raw_console.log --hz 16e6 \
	    --out $(BUILD)/mcu/st-iotnode.analysis.json > /dev/null
	$(PY) -m mcu.analyze results/mcu/xai-nucleo-l476rg/raw.log --hz 16e6 \
	    --out $(BUILD)/mcu/nucleo-l476rg.analysis.json > /dev/null
	@echo "-> $(BUILD)/mcu/ (compare with results/mcu/*/analysis.json)"

# Lab runs; need accounts on the testbeds (see README).
mcu-iotlab:
	src/mcu/iotlab_run.sh 40 xai-st-iotnode-rerun 1

mcu-shepherd:
	$(PY) -m mcu.shepherd_run firmware/xai_nrf52840.elf --duration 900 --name xai-nrf52840-rerun

clean:
	rm -rf $(BUILD) out src/mcu/model.h
	find src -name __pycache__ -type d -prune -exec rm -rf {} +
