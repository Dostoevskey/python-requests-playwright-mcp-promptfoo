# Local Test Automation Stack

Automation workspace that provisions the Conduit RealWorld demo app, seeds deterministic data, and runs API, UI, and LLM prompt validation entirely on local infrastructure.

## Features
- Automated bootstrap script clones the demo app, configures PostgreSQL, and applies migrations.
- Deterministic seed data creates five users and ten articles through the public API.
- Health guardrails verify frontend, backend, and database readiness before pytest executes.
- Pytest suites cover REST CRUD operations, authentication, pagination, and Playwright UI flows with multi-context support (desktop + mobile).
- Allure reporting baked into every run with attachments for API responses, Playwright traces, and LLM outputs.
- Prompt evaluation harness built on Ollama + Promptfoo with small local models (`gemma3:4b`, `deepseek-r1:8b`) and judge validation via `gpt-oss:20b`.
- GitHub Actions CI pipeline validates the API, UI, and LLM suites and archives Allure bundles for every push/PR.

## Project Layout
```
.
├── config/               # Environment, seed, and promptfoo configs
├── demo-app/             # RealWorld app clone target (ignored by git)
├── scripts/              # Bootstrap, seeding, and health utilities
├── src/                  # Shared helpers (API client, health, ollama)
├── tests/
│   ├── api/              # Requests-based API coverage
│   ├── ui/               # Playwright MCP multi-context UI coverage
│   └── llm/              # Promptfoo + Ollama integration tests
├── promptfoo/            # Prompt templates and reference repo snapshot
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
   make demo:setup        # Clones repo, installs workspaces, writes backend .env, runs migrations
   make demo:seed         # Populates five users + ten articles through the public API
   ```

   > The `demo-app/src` directory is ignored by git so you can safely re-run or reset using `make demo:reset`.

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
`config/promptfoo.yaml` defines three article-drafting scenarios targeting `gemma3:4b` and `deepseek-r1:8b`. Every scenario enforces:
- 300–500 character output length (JavaScript assertion).
- LLM rubric validation using `gpt-oss:20b` to guard against hallucinations and off-topic responses.

Run the suite:
```bash
make promptfoo
# or watch mode
make promptfoo-watch
```

### Pytest + Ollama
`tests/llm/test_article_generation.py` reads prompt templates from `promptfoo/prompts/articles.yaml`, renders them with Jinja2, and uses `OllamaRunner` to:
1. Generate content with each lightweight model.
2. Ensure character-length compliance.
3. Ask `gpt-oss:20b` to adjudicate coherence and topical accuracy.

Outputs, prompts, and judge decisions are attached to Allure for traceability.

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

## Next Steps
- Wire this project into CI by reusing `make install` + health checks before running targeted suites.
- Extend API and UI fixtures with data builders for more complex CRUD scenarios (comments, tags, favorites).
- Add synthetic monitoring jobs that run the health script on a schedule to catch environment regressions early.
