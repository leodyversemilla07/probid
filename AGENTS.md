# AGENTS.md

Agent guidance for probid.

This file is the single source of instructions for coding agents working in this repository.

## Project overview

- Project: probid
- Purpose: Provide a minimal terminal probing agent harness for Philippine government procurement with local-first, explainable heuristics
- Stack: Python, Click CLI, Playwright, Rich, SQLite
- Data source: PhilGEPS notices site
- Legal baseline: RA 12009 + IRR

## Setup commands

- Install deps: `uv sync`
- Install dev tools (ruff, ty): `uv sync --extra dev`
- Install browser (optional): `uv sync --extra browser` or `uv sync --all-extras`
- Run linter: `uv run ruff check packages/`
- Format code: `uv run ruff format packages/`
- Check linting/formatting: `uv run ruff check packages/ && uv run ruff format --check packages/`
- Run type checker: `uv run ty check`
- Run CLI help: `probid --help`
- Run package test suite: `python3 scripts/run_tests.py`
- Run package test suite via Make: `make test`
- Run probe contract test directly: `PYTHONPATH=packages/probing-agent/src:packages/agent/src:packages/ai/src:packages/tui/src python3 -m unittest packages/probing-agent/tests/test_probe_output_contract.py -v`

## Common run commands

- Probe (summary-first): `probid probe "laptop"`
- Agent harness shell: `probid` (default interactive)
- Agent harness shell alias: `probid agent`
- One-shot harness query (text): `probid -q "probe laptop"`
- One-shot harness query (JSON): `probid -q "probe laptop" --json-output`
- Continue most recent persisted session: `probid -q "explain the top finding" --session-dir .probid-sessions --continue-recent --json-output`
- Export recent session as JSON content only: `probid -q "turn this into json" --session-dir .probid-sessions --continue-recent --export-output --output export.json`
- Export recent session as Markdown report: `probid -q "make this a markdown report" --session-dir .probid-sessions --continue-recent --export-output --output report.md`
- Export recent session as analyst handoff: `probid -q "generate a handoff note for another analyst" --session-dir .probid-sessions --continue-recent --export-output --output handoff.json`
- Export recent session as CSV summary: `probid -q "export a csv summary" --session-dir .probid-sessions --continue-recent --export-output --output summary.csv`
- Export recent session as case timeline: `probid -q "make this a case timeline" --session-dir .probid-sessions --continue-recent --export-output --output timeline.md`
- Export recent session as findings table: `probid -q "turn this into a findings table" --session-dir .probid-sessions --continue-recent --export-output --output findings-table.md`
- Inspect last export destination from the current session: `probid -q "show last export destination" --session-dir .probid-sessions --continue-recent --json-output`
- Inspect last export format from the current session: `probid -q "what was the last export format?" --session-dir .probid-sessions --continue-recent --json-output`
- List prior exports from the current session: `probid -q "list prior exports" --session-dir .probid-sessions --continue-recent --json-output`
- Re-export the last persisted artifact to a new file: `probid -q "re-export the last artifact" --session-dir .probid-sessions --continue-recent --export-output --output export-copy.json`
- Re-export the last markdown report to a new file: `probid -q "re-export the last markdown report" --session-dir .probid-sessions --continue-recent --export-output --output report-copy.md`
- Inspect persisted export artifacts directly: `probid exports --session-dir .probid-sessions`
- Inspect persisted export artifacts as JSON: `probid exports --session-dir .probid-sessions --json`
- Filter persisted export artifacts by format: `probid exports --session-dir .probid-sessions --format markdown`
- Inspect a specific session by full id or unique prefix: `probid exports --session-dir .probid-sessions --session-id abcd1234`
- List exports across all sessions: `probid exports --session-dir .probid-sessions --all`
- Limit exports displayed: `probid exports --session-dir .probid-sessions --limit 10`
- Combine filtering across all sessions: `probid exports --session-dir .probid-sessions --all --format json --limit 20`
- Use `.md` / `.markdown` for markdown-style exports, `.csv` for CSV summaries, and `.json` for structured exports.
- Export artifact metadata is persisted as session events and can be queried with session-aware follow-ups.
- Manual validation for export-audit workflows should cover: create an export, then run `show last export destination`, `list prior exports`, and `re-export the last artifact` against the same persisted session.
- Harness session logging is disabled by default. Enable with `PROBID_AGENT_LOG_SESSION=1`.
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

- CLI entrypoint: `packages/probing-agent/src/probid_probing_agent/cli.py`
- CLI helpers and commands: `packages/probing-agent/src/probid_probing_agent/cli/`
- Probing agent runtime: `packages/probing-agent/src/probid_probing_agent/core/`
- Interactive harness mode: `packages/probing-agent/src/probid_probing_agent/modes/interactive/`
- Package-local tests: `packages/probing-agent/tests/`
- Agent core package: `packages/agent/src/probid_agent/`
- AI package: `packages/ai/src/probid_ai/`
- Terminal UI package: `packages/tui/src/probid_tui/`

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
