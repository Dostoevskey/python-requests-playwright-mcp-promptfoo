PYTHON ?= python3
PIP ?= pip3
PLAYWRIGHT_BROWSER ?= chromium

install:
	$(PYTHON) -m pip install -r requirements.txt
	npm install
	$(PYTHON) -m playwright install --with-deps $(PLAYWRIGHT_BROWSER)

lint:
	$(PYTHON) -m pytest --collect-only

check:health:
	$(PYTHON) scripts/health_check.py --env-file config/demo.env

promptfoo:
	npm run promptfoo:test

promptfoo-watch:
	npm run promptfoo:test:watch

DemoSetup: demo:setup

demo\:setup:
	bash scripts/bootstrap_demo_app.sh

DemoSeed: demo:seed

demo\:seed:
	$(PYTHON) scripts/seed_demo_data.py --env-file config/demo.env

DemoReset: demo:reset

demo\:reset:
	bash scripts/bootstrap_demo_app.sh --reset
	$(PYTHON) scripts/seed_demo_data.py --env-file config/demo.env

PlaywrightUI: test:ui

test\:api:
	pytest -m api

test\:ui:
	pytest -m ui --headed

test\:llm:
	pytest -m llm

test:
	pytest

report:
	allure serve allure-results

.PHONY: install lint check\:health promptfoo promptfoo-watch demo\:setup demo\:seed demo\:reset test\:api test\:ui test\:llm test report
