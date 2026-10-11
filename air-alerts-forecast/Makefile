PYTHON ?= python
IMAGE ?= air-alerts-forecast:local

.PHONY: all build test smoke run data features train evaluate validate-leakage agents clean

all: data features train evaluate

build:
	docker build -t $(IMAGE) .

test:
	$(PYTHON) -m pytest tests/ -v

smoke:
	$(PYTHON) -m src.pipeline all --config config.smoke.yaml
	$(PYTHON) -c "from pathlib import Path; p=Path('outputs/smoke/metrics/smoke_metrics.json'); assert p.is_file() and p.stat().st_size > 0"

run:
	docker run --rm -v "$(CURDIR)/outputs:/app/outputs" -e DATABASE_URL $(IMAGE) python -m src.pipeline all --config config.yaml

agents:
	$(PYTHON) -m src.agents.orchestrator --config config.yaml --output outputs/agents

data:
	$(PYTHON) -m src.pipeline data --config config.yaml

features:
	$(PYTHON) -m src.pipeline features --config config.yaml

train:
	$(PYTHON) -m src.pipeline train --config config.yaml

evaluate:
	$(PYTHON) -m src.pipeline evaluate --config config.yaml

validate-leakage:
	$(PYTHON) -m src.validate_no_leakage --config config.yaml

clean:
	$(PYTHON) -c "import shutil,os; [shutil.rmtree(os.path.join('outputs',d),ignore_errors=True) for d in ['figures','metrics','predictions','agents','runs']]"
