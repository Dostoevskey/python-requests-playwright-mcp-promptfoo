# Local Test Automation Stack

Automation workspace that provisions the Conduit RealWorld demo app, seeds deterministic data, and runs API, UI, and LLM prompt validation entirely on local infrastructure.

## Features
- Bundled Conduit RealWorld demo app with a bootstrap script that installs dependencies and runs migrations without additional git clones.
- Deterministic seed data creates five users and ten articles through the public API.
- Health guardrails verify frontend, backend, and database readiness before pytest executes.
- Pytest suites cover REST CRUD operations, authentication, pagination, and Playwright UI flows with multi-context support (desktop + mobile).
- Allure reporting baked into every run with attachments for API responses, Playwright traces, and LLM outputs.
- Prompt evaluation harness built on Ollama + Promptfoo with small local models (`gemma3:4b`, `deepseek-r1:8b`) and judge validation via `gpt-oss:20b`.
- Bundled prompt suites derived from `llm-prompt-testing-quick-start`, each with its own configuration for independent evaluation.
- GitHub Actions CI pipeline validates the API, UI, and LLM suites and archives Allure bundles for every push/PR.
- Optional Playwright MCP server integration for interactive locator capture from the same workspace.

## Project Layout
```
.
├── config/               # Environment, seed, and promptfoo configs
├── demo-app/             # Vendored RealWorld example app (frontend + backend sources)
├── scripts/              # Bootstrap, seeding, and health utilities
├── src/                  # Shared helpers (API client, health, ollama)
├── tests/
│   ├── api/              # Requests-based API coverage
│   ├── ui/               # Playwright MCP multi-context UI coverage
│   └── llm/              # Promptfoo + Ollama integration tests
├── promptfoo/            # Offline prompt suites and shared templates
├── docker-compose.yml    # Optional container stack for postgres/backend/frontend
├── Makefile              # Friendly entry points
├── pyproject.toml        # Python dependencies + pytest config
└── package.json          # Node dependencies for promptfoo
```

## Prerequisites
- Python 3.10+ with `pip` and virtual environment support (`python3-venv` on Debian/Ubuntu).
- Node.js 18+ (needed for the demo app and Promptfoo CLI).
- Docker + Docker Compose (optional but simplifies demo app + PostgreSQL orchestration).
- Allure command line (`brew install allure`, `scoop install allure`, or download from JetBrains).
- Ollama installed locally with access to the following models:
  - `ollama pull gemma3:4b`
  - `ollama pull deepseek-r1:8b`
  - `ollama pull gpt-oss:20b`
- PostgreSQL client tools (`psql`) for migrations and health checks.

## Quick Start

1. **Install Python dependencies**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. **Install Node dependencies**
   ```bash
   npm install
   ```

3. **Provision the RealWorld demo app**
   ```bash
   make demo:setup        # Installs workspaces, writes backend .env, runs migrations
   make demo:seed         # Populates five users + ten articles through the public API
   ```

   > The RealWorld frontend + backend sources ship with this repository. `make demo:reset` simply removes workspace `node_modules` before reinstalling.

4. **Launch the stack**
   - **With Docker Compose**
     ```bash
     docker compose up postgres -d
     docker compose up demo-backend demo-frontend
     ```
   - **Manual (two terminals)**
     ```bash
     (cd demo-app/src && npm run dev)  # starts backend (3001) + frontend (3000)
     ```

5. **Run readiness checks**
 ```bash
 make check:health
 ```

> After the first `pip`/`npm` install, no additional GitHub clones are required—the RealWorld app and prompt suites are fully vendored in this repository so the entire test stack can run offline.

## Test Suites

| Command | Description |
|---------|-------------|
| `make test:api` | Requests-based CRUD, auth, and pagination tests. |
| `make test:ui` | Playwright MCP multi-context runs (`--headed` is enforced for IDE-friendly inspector). |
| `make test:llm` | Ollama-powered article generation checks plus Promptfoo evaluation wrapper. |
| `make test` | Runs the entire pytest suite. |

All pytest runs write Allure results to `allure-results/`. Generate a report via:

```bash
make report         # opens Allure dashboard in a browser
```

### Health-Aware Fixtures
- `tests/conftest.py` loads `config/demo.env`, asserts backend/frontend/database readiness, and surfaces metadata to Allure.
- API tests rely on `src/utils/api_client.py` for clean request helpers and token management.
- UI tests (`tests/ui/test_articles_ui.py`) exercise login, article authoring, pagination, and authenticated routing using dual browser contexts (desktop + mobile) configured in `tests/ui/conftest.py`.

## Prompt Evaluation

### Promptfoo Workflow
Each prompt suite lives under `promptfoo/suites/<name>`. They are adapted from the `llm-prompt-testing-quick-start` repository and reworked to run entirely on local Ollama models. Evaluate the bundled article writer suite with:
```bash
make promptfoo
# or watch mode
make promptfoo-watch
```

Available suites:

- `articles` – structured article drafting with rubric enforcement.
- `is_nlq_agent_prompt` – JSON scoring of NLQ questions.
- `is_nlq_minimal_agent_prompt` – lightweight yes/no validation.
- `nlq_to_sql` – SQL synthesis with aggregate queries.
- `nlq_to_sql_experiment` – JOIN-focused SQL prompts.
- `try_this_nlq_agent_prompt` – natural language question generation with row limits.

You can run an individual suite with `npx promptfoo eval --config promptfoo/suites/<suite>/promptfooconfig.yaml`.

### Pytest + Ollama
`tests/llm/test_article_generation.py` reads prompt templates from `promptfoo/prompts/articles.yaml`, renders them with Jinja2, and uses `OllamaRunner`/`gpt-oss:20b` to:
1. Generate content with each lightweight model.
2. Ensure character-length compliance.
3. Ask `gpt-oss:20b` to adjudicate coherence and topical accuracy.

Outputs, prompts, and judge decisions are attached to Allure for traceability.

### Playwright MCP (Optional)
Launch the MCP helper to capture DOM snippets and selectors while the RealWorld frontend is running:

```bash
npm run mcp -- --url http://localhost:3000/#/
```

The server exposes Model Context Protocol commands that tools like Cursor or Claude can consume to generate Playwright flows. See the in-terminal instructions for details.

## Setup Notes
- The repository intentionally ignores `demo-app/src/` and `promptfoo/source/` so you can freely update upstream projects without polluting Git history.
- Update `config/demo.env` to align with custom ports, database credentials, or Ollama endpoints.
- If you rely on Docker, ensure `demo-app/src` exists before `docker compose up` so volume mounts succeed.

## Troubleshooting
- **Missing Python packages** – create a virtual environment (`python3 -m venv .venv`) before installing `requirements.txt`.
- **`ollama` errors** – confirm the daemon is running (`ollama serve`) and models are pulled locally.
- **Promptfoo CLI not found** – run `npm install` to place `promptfoo` in `node_modules/.bin`, or invoke via `npx promptfoo`.
- **Playwright browsers missing** – after `pip install`, run `python -m playwright install --with-deps chromium`.
- **Allure CLI unavailable** – install globally or use Docker (`docker run -p 4040:4040 -v $PWD/allure-results:/app/results frankescobar/allure-docker-service`).
- **GitHub Actions failures** – review `.github/workflows/ci.yml` to replay `npm install`, `python scripts/health_check.py`, `python scripts/seed_demo_data.py`, and `python -m pytest` locally, then inspect uploaded Allure artifacts from the workflow run.

## Known Gaps & Future Enhancements
- The bundled Ollama models can still produce unstable text; adding deterministic mock providers would make CI faster and more predictable.
- PostgreSQL migrations currently run synchronously via `npm run sqlz`; packaging a SQLite-backed demo would remove the Docker requirement for quick smoke tests.
- UI tests rely on the real browser; introducing visual regression snapshots or contract tests for the MCP output would broaden coverage.
