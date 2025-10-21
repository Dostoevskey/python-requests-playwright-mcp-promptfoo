# Playwright MCP Server Notes

The repository bundles the [`playwright-mcp`](https://www.npmjs.com/package/playwright-mcp) package as a development dependency so you can spin up the Model Context Protocol helper directly inside this workspace. This document captures practical usage patterns for the RealWorld demo application.

## Launching the server

1. Ensure the demo app is running locally (for example: `make demo:setup` followed by `(cd demo-app/src && npm run dev)`).
2. Start the MCP bridge:

   ```bash
   npm run mcp -- --url http://localhost:3000/#/
   ```

   The additional `--url` flag instructs the server to point at the RealWorld frontend. Adjust the address if you expose the site under a different host/port.

## Typical workflows

### Interactive locator harvesting
- Use an MCP-aware client (Cursor, Claude Desktop, MCP CLI, etc.) to connect to the server.
- Invoke `init-browser`, then leverage the "pick DOM" tool to capture CSS/XPath selectors or screenshots.
- Paste the generated selectors into Playwright tests (for example `tests/ui/test_articles_ui.py`) to speed up authoring.

### Rapid UI script prototyping
- The `execute-code` command executes arbitrary Playwright snippets against the current page.
- Draft a flow interactively, verify it succeeds in the MCP session, then port the refined script into a permanent test.

### DOM/screenshot context for LLM prompts
- `get-context`, `get-full-dom`, and `get-screenshot` commands provide structured data about the live UI.
- Feed these artifacts into Promptfoo suites when crafting new evaluation scenarios so the prompts stay aligned with the actual UI.

## Automation ideas
- Add a `make mcp` target (aliasing `npm run mcp`) for discoverability.
- Wrap the server inside Docker Compose to run alongside the demo app when locator exploration is needed.
- Persist MCP-captured traces as Allure attachments during exploratory runs to document selector provenance.

> The MCP server is intentionally optional—it does not run in CI. Treat it as a productivity booster when curating new Playwright flows or LLM prompt examples.
