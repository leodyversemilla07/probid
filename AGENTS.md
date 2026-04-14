# AGENTS.md

Agent guidance for probid.

This file is the single source of instructions for coding agents working in this repository.

## Project overview

- Project: probid
- Purpose: Probe Philippine government procurement with local-first, explainable heuristics
- Stack: Python, Click CLI, Playwright, Rich, SQLite
- Data source: PhilGEPS notices site
- Legal baseline: RA 12009 + IRR

## Setup commands

- Install deps: `uv sync`
- Install browser (optional): `uv sync --all-extras && playwright install chromium`
- Run CLI help: `probid --help`
- Run probe contract tests: `PYTHONPATH=src python3 -m unittest tests/test_probe_output_contract.py -v`

## Common run commands

- Probe (summary-first): `probid probe "laptop"`
- Agent shell: `probid` (default interactive)
- Agent shell alias: `probid agent`
- One-shot agent query (text): `probid -q "probe laptop"`
- One-shot agent query (JSON): `probid -q "probe laptop" --json-output`
- Agent session logging is disabled by default. Enable with `PROBID_AGENT_LOG_SESSION=1`.
- Local auth file for `/login` and `/logout`: `~/.probid/auth.json` (override with `PROBID_AUTH_FILE`).
- GitHub Copilot aliases supported in REPL auth: `copilot`, `github copilot`, `github-copilot`.
- Probe with evidence/caveats: `probid probe "laptop" --why`
- Probe JSON output: `probid probe "laptop" --json`
- Probe confidence filter: `probid probe "laptop" --min-confidence medium`
- Probe capped findings: `probid probe "laptop" --max-findings 3`
- Search notices: `probid search "laptop"`
- Search with details: `probid search "server" --pages 3 --detail`
- Notice detail: `probid detail 12905086`
- Awards: `probid awards`
- Agency profile: `probid agency "DICT"`
- Supplier profile: `probid supplier "ACME CORPORATION"`
- Overprice heuristic: `probid overprice "laptop" --threshold 150`
- Repeat awardees: `probid repeat --min-count 3`
- Split-contract heuristic: `probid split "DICT" --gap-days 30`

## Architecture

- CLI entrypoint: `src/app/cli.py`
- Commands: `src/app/commands/`
- Scraper source connector: `src/app/sources/philgeps.py`
- Cache and models: `src/app/data/`
- Heuristics: `src/app/analysis/`
- Terminal rendering: `src/app/ui/display.py`

## Coding rules

1) Preserve minimalism
- Prefer small, focused changes.
- Do not add new top-level commands unless necessary.
- Keep defaults simple; add depth via flags.

2) Keep outputs explainable
- Every risk flag should be traceable to evidence fields.
- Prefer interpretable heuristics over opaque scoring.
- Flag risk; do not imply legal guilt.

3) Local-first by default
- Reuse SQLite cache whenever possible.
- Avoid paid dependencies or cloud-only design.

4) Legal consistency
- Use RA 12009 + IRR semantics for procurement logic.
- Treat RA 9184-era assumptions as legacy unless explicitly requested.

## Scraping notes (PhilGEPS)

- Site is ASP.NET WebForms.
- Search input appears after clicking the Search link/postback.
- Use stable selectors (`#txtKeyword`, `#btnSearch`) after search mode is active.
- Budget is often on detail pages, not list pages.
- Favor retry + graceful fallback to cache on scrape failure.

## Guardrails

- Do not fabricate data.
- Be explicit about uncertainty and missing fields.
- Prefer reversible edits and small PR-sized diffs.
- Maintain source traceability in outputs.

## Definition of done for changes

- Command behavior remains backward compatible unless explicitly changed.
- README and AGENTS.md are updated if UX or workflow changed.
- New heuristic includes: trigger, evidence, confidence, false-positive note.
- Basic manual validation run completed with at least one representative command.

## Non-goals

- Not a legal adjudication engine.
- Not a replacement for formal audit/investigation bodies.
- Not a dashboard-heavy platform.
