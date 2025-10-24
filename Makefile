PYTHON ?= python3
PIP ?= pip3
PLAYWRIGHT_BROWSER ?= chromium
PYTEST ?= $(PYTHON) -m pytest
ENV_FILE ?= config/demo.env
CI_FLAG := $(shell echo "$(CI)" | tr A-Z a-z)
PYTHONPATH := $(if $(PYTHONPATH),$(PYTHONPATH):,).
export PYTHONPATH

ifdef USE_FAKE_OLLAMA
LLM_USE_FAKE := $(USE_FAKE_OLLAMA)
else
LLM_USE_FAKE := $(if $(filter true yes 1,$(CI_FLAG)),1,0)
endif

ifeq ($(strip $(LLM_USE_FAKE)),0)
PYTEST_DISTRIBUTION ?=
else
PYTEST_DISTRIBUTION ?= -n auto
endif
UI_ENV_FILE := $(or $(DEMO_ENV_FILE),$(ENV_FILE))

install:
	$(PYTHON) -m pip install -r requirements.txt
	npm install
	$(PYTHON) -m playwright install --with-deps $(PLAYWRIGHT_BROWSER)

compose\:up:
	docker compose up -d postgres demo-backend demo-frontend

compose\:down:
	docker compose down

lint:
	$(PYTHON) -m pytest --collect-only

check\:health:
	$(PYTHON) scripts/health_check.py --env-file config/demo.env

promptfoo:
	npm run promptfoo:test

promptfoo-watch:
	npm run promptfoo:test:watch

DemoSetup: demo\:setup

demo\:setup:
	bash scripts/bootstrap_demo_app.sh

DemoSeed: demo\:seed

demo\:seed:
	docker compose up -d postgres demo-backend demo-frontend
	$(PYTHON) scripts/health_check.py --env-file config/demo.env
	sleep 3
	$(PYTHON) scripts/seed_demo_data.py --env-file config/demo.env

DemoReset: demo\:reset

demo\:reset:
	bash scripts/bootstrap_demo_app.sh --reset
	$(PYTHON) scripts/seed_demo_data.py --env-file config/demo.env

PlaywrightUI: test\:ui

test\:api:
	@bash -c 'set -euo pipefail; \
		docker compose up -d postgres demo-backend demo-frontend; \
		trap "docker compose down" EXIT; \
		$(PYTHON) scripts/health_check.py --env-file "$(ENV_FILE)"; \
		sleep 3; \
		$(PYTHON) scripts/seed_demo_data.py --env-file "$(ENV_FILE)"; \
		PYTHONPATH=. $(PYTEST) -m api'

test\:ui:
	@bash -c 'set -euo pipefail; \
		docker compose up -d postgres demo-backend demo-frontend; \
		trap "docker compose down" EXIT; \
		$(PYTHON) scripts/health_check.py --env-file "$(ENV_FILE)"; \
		sleep 3; \
		$(PYTHON) scripts/seed_demo_data.py --env-file "$(ENV_FILE)"; \
		PYTHONPATH=. $(PYTEST) -m ui --headed'

test\:smoke:
	@bash -c 'set -euo pipefail; \
		docker compose up -d postgres demo-backend demo-frontend; \
		trap "docker compose down" EXIT; \
		$(PYTHON) scripts/health_check.py --env-file "$(ENV_FILE)"; \
		sleep 2; \
		PYTHONPATH=. $(PYTEST) -m smoke --maxfail=1 --alluredir=allure-results --clean-alluredir'

test\:llm:
	@bash -c 'set -euo pipefail; \
		docker compose up -d postgres demo-backend demo-frontend; \
		trap "docker compose down" EXIT; \
		$(PYTHON) scripts/health_check.py --env-file "$(ENV_FILE)"; \
		sleep 3; \
		$(PYTHON) scripts/seed_demo_data.py --env-file "$(ENV_FILE)"; \
		PYTHONPATH=. $(PYTEST) -m llm'

test\:llm\:audit:
	@bash -c 'set -euo pipefail; \
		docker compose up -d postgres demo-backend demo-frontend; \
		trap "docker compose down" EXIT; \
		$(PYTHON) scripts/health_check.py --env-file "$(ENV_FILE)"; \
		sleep 3; \
		$(PYTHON) scripts/seed_demo_data.py --env-file "$(ENV_FILE)"; \
		echo ""; \
		echo "⚠️  STRICT QUALITY AUDIT MODE ⚠️"; \
		echo "This test uses zero retries and may FAIL with small models."; \
		echo "Failures demonstrate the test framework can detect LLM defects."; \
		echo "Review Allure attachments for detailed failure analysis."; \
		echo ""; \
		PYTHONPATH=. $(PYTEST) -m llm_audit --verbose'

test:
	@bash -c 'set -euo pipefail; \
		start_ts=$$(date +%s); \
		TEARDOWN_DONE=0; \
		TEARDOWN_TIME=0; \
		cleanup() { \
			if [ "$$TEARDOWN_DONE" -eq 0 ]; then \
				local teardown_start=$$(date +%s); \
				docker compose down; \
				local teardown_end=$$(date +%s); \
				TEARDOWN_TIME=$$((teardown_end - teardown_start)); \
				TEARDOWN_DONE=1; \
			fi; \
		}; \
		trap cleanup EXIT; \
		echo "==> Spinning up demo stack"; \
		docker compose up -d postgres demo-backend demo-frontend; \
		$(PYTHON) scripts/health_check.py --env-file "$(ENV_FILE)"; \
		sleep 3; \
		$(PYTHON) scripts/seed_demo_data.py --env-file "$(ENV_FILE)"; \
		setup_end=$$(date +%s); \
		SETUP_TIME=$$((setup_end - start_ts)); \
		rm -rf allure-results; \
		mkdir -p allure-results; \
		phase() { \
			local var_name="$$1"; shift; \
			local phase_start=$$(date +%s); \
			"$$@"; \
			local phase_end=$$(date +%s); \
			printf -v "$$var_name" "%d" $$((phase_end - phase_start)); \
		}; \
		echo "==> API tests"; \
		phase API_TIME env USE_FAKE_OLLAMA=$(LLM_USE_FAKE) PYTHONPATH=. \
			$(PYTEST) $(PYTEST_DISTRIBUTION) -m api \
			--reruns 1 --alluredir=allure-results --clean-alluredir; \
		echo "==> UI tests"; \
		phase UI_TIME env USE_FAKE_OLLAMA=$(LLM_USE_FAKE) PYTHONPATH=. \
			$(PYTEST) $(PYTEST_DISTRIBUTION) -m ui \
			--reruns 1 --alluredir=allure-results; \
		echo "==> LLM smoke tests"; \
		phase LLM_TIME env USE_FAKE_OLLAMA=$(LLM_USE_FAKE) PYTHONPATH=. \
			$(PYTEST) $(PYTEST_DISTRIBUTION) -m "llm and not llm_audit" \
			--reruns 1 --alluredir=allure-results; \
		echo "==> LLM audit (lightweight)"; \
		phase LLM_AUDIT_TIME env USE_FAKE_OLLAMA=$(LLM_USE_FAKE) PYTHONPATH=. \
			$(PYTEST) $(PYTEST_DISTRIBUTION) -m llm_audit \
			--reruns 1 --alluredir=allure-results; \
		trap - EXIT; \
		cleanup; \
		total_end=$$(date +%s); \
		TOTAL_TIME=$$((total_end - start_ts)); \
		printf "\nPhase durations (seconds):\n"; \
		printf "  setup: %s\n" "$$SETUP_TIME"; \
		printf "  api: %s\n" "$$API_TIME"; \
		printf "  ui: %s\n" "$$UI_TIME"; \
		printf "  llm: %s\n" "$$LLM_TIME"; \
		printf "  llm_audit: %s\n" "$$LLM_AUDIT_TIME"; \
		printf "  teardown: %s\n" "$$TEARDOWN_TIME"; \
		printf "  total: %s\n" "$$TOTAL_TIME"; \
		echo ""; \
		echo "Allure results available in allure-results/"; \
	'

report:
	allure serve allure-results

.PHONY: install compose\:up compose\:down lint check\:health promptfoo promptfoo-watch demo\:setup demo\:seed demo\:reset test\:api test\:ui test\:smoke test\:llm test\:llm\:audit test report
