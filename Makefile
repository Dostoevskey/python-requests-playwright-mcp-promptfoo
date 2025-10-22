PYTHON ?= python3
PIP ?= pip3
PLAYWRIGHT_BROWSER ?= chromium
PYTEST ?= pytest
ENV_FILE ?= config/demo.env
CI_FLAG := $(shell echo "$(CI)" | tr A-Z a-z)
LLM_USE_FAKE := $(if $(filter true yes 1,$(CI_FLAG)),1,0)
UI_ENV_FILE := $(or $(DEMO_ENV_FILE),$(ENV_FILE))

install:
	$(PYTHON) -m pip install --upgrade pip --break-system-packages
	$(PYTHON) -m pip install -r requirements.txt --break-system-packages
	npm install --prefer-offline --no-fund
	$(PYTHON) -m playwright install $(PLAYWRIGHT_BROWSER)

lint:
	$(PYTEST) --collect-only

check\:health:
	$(PYTHON) scripts/health_check.py --env-file config/demo.env

demo\:setup:
	bash scripts/bootstrap_demo_app.sh

demo\:lite:
	DB_DIALECT=sqlite DB_STORAGE=./demo-app/realworld.sqlite USE_FAKE_OLLAMA=1 bash scripts/bootstrap_demo_app.sh --reset

promptfoo:
	npm run promptfoo:test

promptfoo-watch:
	npm run promptfoo:test:watch

promptfoo-view:
	npm run promptfoo:view

mcp:
	npm run mcp

demo\:servers\:start:
	python scripts/manage_demo_servers.py start --env-file $(ENV_FILE)

demo\:servers\:stop:
	python scripts/manage_demo_servers.py stop --env-file $(ENV_FILE)

demo\:servers\:status:
	python scripts/manage_demo_servers.py status --env-file $(ENV_FILE)

logs\:clean:
	rm -f logs/*.log logs/*.log.*

test\:smoke:
	USE_FAKE_OLLAMA=$(LLM_USE_FAKE) $(PYTEST) -m smoke --maxfail=1 --reruns 1

test\:api:
	$(PYTEST) -m api --reruns 1 -n auto

test\:ui:
	@bash -c 'set -euo pipefail; \
	ENV_FILE="$(UI_ENV_FILE)"; \
	trap "python scripts/manage_demo_servers.py stop --env-file \"$$ENV_FILE\" || true" EXIT; \
	python scripts/manage_demo_servers.py start --env-file "$$ENV_FILE"; \
	PLAYWRIGHT_RECORD=1 PLAYWRIGHT_HEADLESS=0 $(PYTEST) -m ui --headed --reruns 1'

test\:ui\:fast:
	@bash -c 'set -euo pipefail; \
	ENV_FILE="$(UI_ENV_FILE)"; \
	trap "python scripts/manage_demo_servers.py stop --env-file \"$$ENV_FILE\" || true" EXIT; \
	python scripts/manage_demo_servers.py start --env-file "$$ENV_FILE"; \
	PLAYWRIGHT_RECORD=0 PLAYWRIGHT_HEADLESS=1 $(PYTEST) -m ui --reruns 1 --disable-warnings'

test\:ui\:parallel:
	@bash -c 'set -euo pipefail; \
	ENV_FILE="$(UI_ENV_FILE)"; \
	trap "python scripts/manage_demo_servers.py stop --env-file \"$$ENV_FILE\" || true" EXIT; \
	python scripts/manage_demo_servers.py start --env-file "$$ENV_FILE"; \
	PLAYWRIGHT_RECORD=0 PLAYWRIGHT_HEADLESS=1 $(PYTEST) -m ui -n auto --dist=loadscope --reruns 2'

test\:llm:
	USE_FAKE_OLLAMA=$(LLM_USE_FAKE) $(PYTEST) -m llm --reruns 1

test:
	USE_FAKE_OLLAMA=$(LLM_USE_FAKE) $(PYTEST) -n auto --reruns 1

report:
	allure serve allure-results

.PHONY: install lint check\:health demo\:setup demo\:lite promptfoo promptfoo-watch promptfoo-view mcp logs\:clean test\:smoke test\:api test\:ui test\:ui\:fast test\:ui\:parallel test\:llm test report
