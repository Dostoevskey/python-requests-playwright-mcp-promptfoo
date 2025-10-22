# Local Test Automation Stack

Automation workspace that provisions the Conduit RealWorld demo app, seeds deterministic data, and runs API, UI, and LLM prompt validation entirely on local infrastructure.

## Features
- Bundled RealWorld frontend + backend so setup works entirely offline (no extra git clones).
- Deterministic seed data creates five users and ten articles through the public API.
- Health guardrails verify frontend, backend, and database readiness before pytest executes.
- Pytest suites cover REST CRUD operations, authentication, pagination, and Playwright UI flows with multi-context support (desktop + mobile).
- Allure reporting baked into every run with attachments for API responses, Playwright traces, and LLM outputs.
- Prompt evaluation harness built on Ollama + Promptfoo with small local models (`gemma3:4b`, `deepseek-r1:8b`) and judge validation via `gpt-oss:20b`).
- GitHub Actions CI pipeline validates the API, UI, and LLM suites and archives Allure bundles for every push/PR.
- Optional Playwright MCP server integration for interactive locator capture (see `docs/playwright-mcp-notes.md`).

## Project Layout
```
.
├── config/               # Environment, seed, and promptfoo configs
├── demo-app/             # Vendored RealWorld example app sources
├── docs/                 # MCP and workflow notes
├── scripts/              # Bootstrap, seeding, and health utilities
├── src/                  # Shared helpers (API client, health, ollama)
├── tests/
│   ├── api/              # Requests-based API coverage
│   ├── ui/               # Playwright MCP multi-context UI coverage
│   ├── llm/              # Promptfoo + Ollama integration tests
│   └── smoke/            # 60-second smoke checks
├── promptfoo/            # Offline prompt suites and shared templates
├── docker-compose.yml    # Optional container stack for postgres/backend/frontend
├── Makefile              # Friendly entry points
├── pyproject.toml        # Python dependencies + pytest config
└── package.json          # Node dependencies for promptfoo / MCP
```

## Prerequisites
- Python 3.10+ with `pip` and virtual environment support (`python3-venv` on Debian/Ubuntu).
- Node.js 18+ (needed for the demo app and Promptfoo CLI).
- Docker + Docker Compose (optional; SQLite is the default for local runs, Postgres remains available).
- Allure command line (`brew install allure`, `scoop install allure`, or download from JetBrains).
- Ollama binaries with the Gemma 3 4B, DeepSeek R1 8B, and GPT-OSS 20B models pulled locally (tests assume real inference by default; flip `USE_FAKE_OLLAMA=1` only for fast stubs).
  ```bash
  ollama pull gemma3:4b
  ollama pull deepseek-r1:8b
  ollama pull gpt-oss:20b
  ```
  Tests assume real inference by default; flip `USE_FAKE_OLLAMA=1` only for fast stubs.
  - On CI pipelines you can set `CI=true` (or `USE_FAKE_OLLAMA=1`) to automatically fall back to the lightweight stubs.

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
   make demo:setup        # Installs workspace deps, writes backend .env (sqlite by default), runs migrations
   make demo:seed         # Populates five users + ten articles through the public API
   ```

   > Need a clean slate? `make demo:lite` removes workspace node_modules and rebuilds everything in sqlite mode.

4. **Launch the stack**
   - **Docker Compose (Postgres)**
     ```bash
     docker compose up postgres -d
     docker compose up demo-backend demo-frontend
     ```
   - **Manual (SQLite, default)**
     ```bash
     (cd demo-app/src && npm run dev)  # backend on 3001, frontend on 3000
     ```

5. **Run readiness checks**
   ```bash
   make check:health
   ```

   > After the first `pip`/`npm` install, no additional GitHub clones are required—the RealWorld app and prompt suites are fully vendored in this repository so the entire test stack can run offline.

6. **Optional quick smoke**
   ```bash
   make test:smoke
   ```

## Test Suites & Commands

| Command | Description | Typical Runtime |
|---------|-------------|-----------------|
| `make test:smoke` | One API + one headless UI flow | < 60s |
| `make test:api` | Requests-based CRUD, auth, and pagination tests (xdist) | ~40s |
| `make test:ui` | Full Playwright run in headed mode with video/snapshot capture | ~90s |
| `make test:ui:fast` | Headless UI sanity (no video/traces) | ~45s |
| `make test:ui:parallel` | Headless UI with `pytest-xdist` loadscope distribution | ~25s |
| `make test:llm` | Offline-stubbed Promptfoo + Ollama checks | ~30s |
| `make test` | Full suite (`-n auto`, reruns enabled) | ~3m |

All pytest runs write Allure results to `allure-results/`. Generate a report via:

```bash
make report  # opens Allure dashboard in a browser
```

## Prompt Evaluation

Prompt suites live under `promptfoo/suites/<name>` and are adapted from `llm-prompt-testing-quick-start` to run entirely on the fake Ollama backend. Evaluate the article writer suite with:

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

`tests/llm/test_article_generation.py` renders templates from `promptfoo/prompts/articles.yaml` and uses `OllamaRunner` to:
1. Generate content (real models by default, enable stubs with `USE_FAKE_OLLAMA=1`).
2. Ensure character-length compliance.
3. Ask `gpt-oss:20b` (or the stub) to adjudicate coherence and topical accuracy.

Outputs, prompts, and judge decisions are attached to Allure for traceability.

### Playwright MCP (Optional)
Launch the MCP helper to capture DOM snippets and selectors while the RealWorld frontend is running:

```bash
npm run mcp -- --url http://localhost:3000/#/
```

See `docs/playwright-mcp-notes.md` for detailed usage patterns.

## Troubleshooting
- **Missing Python packages** – create a virtual environment (`python3 -m venv .venv`) before installing `requirements.txt`.
- **`ollama` errors** – confirm the daemon is running (`ollama serve`). For faster deterministic runs, you may set `USE_FAKE_OLLAMA=1` to use stubs.
- **Promptfoo CLI not found** – run `npm install` to place `promptfoo` in `node_modules/.bin`, or invoke via `npx promptfoo`.
- **Playwright browsers missing** – after `pip install`, run `python -m playwright install --with-deps chromium`.
- **Allure CLI unavailable** – install globally or use Docker (`docker run -p 4040:4040 -v $PWD/allure-results:/app/results frankescobar/allure-docker-service`).
- **GitHub Actions failures** – review `.github/workflows/ci.yml` to replay `npm install`, `python scripts/health_check.py`, `python scripts/seed_demo_data.py`, and `python -m pytest` locally, then inspect uploaded Allure artifacts from the workflow run.

## Known Gaps & Future Enhancements
- Real Ollama models provide higher-fidelity results; optional stubs remain available via `USE_FAKE_OLLAMA=1` when e2e coverage is not required.
- SQLite keeps setup light; packaging a Postgres flavour (via Docker) remains available for compatibility testing.
- UI tests rely on the real browser; introducing visual regression snapshots beyond the homepage or automated accessibility checks would broaden coverage.

***

For MCP usage tips see `docs/playwright-mcp-notes.md`.
