# probid Product Requirements Document

## 1. Summary

`probid` is a minimal terminal probing agent harness for Philippine public procurement. It helps analysts, journalists, civic technologists, and procurement monitors run local-first, explainable probes against PhilGEPS-derived procurement data.

The product surfaces reason-coded risk signals, not legal conclusions. It prioritizes traceable evidence, clear caveats, and small constrained workflows over broad automation or opaque scoring.

## 2. Problem

Philippine procurement data is public but difficult to triage quickly from the terminal. Users who want to inspect notices, awards, suppliers, and agencies need a workflow that can:

- gather relevant PhilGEPS data,
- reuse a local cache,
- identify suspicious or unusual patterns,
- explain why each pattern was flagged,
- preserve uncertainty and missing-data caveats, and
- export analyst-friendly artifacts for follow-up.

Existing workflows are often manual, dashboard-heavy, cloud-dependent, or insufficiently explainable for audit-style review.

## 3. Goals

- Provide a minimal CLI-first investigation entry point.
- Make `probid probe <query>` the primary workflow for quick triage.
- Keep all risk outputs explainable with evidence fields, confidence, and caveats.
- Use RA 12009 + IRR semantics as the procurement baseline.
- Prefer local SQLite cache reuse and graceful fallback when scraping is unavailable.
- Support session-aware follow-ups and export artifacts without rerunning tools unnecessarily.
- Preserve backward compatibility for existing commands unless explicitly changed.

## 4. Non-goals

- Not a legal adjudication engine.
- Not a replacement for formal audit, investigation, or procurement authorities.
- Not a corruption-verdict generator.
- Not a dashboard-heavy platform.
- Not dependent on paid APIs or cloud-only services.
- Not a full beneficial ownership intelligence system unless reliable data exists locally.

## 5. Target users

### Primary users

- Procurement analysts doing early risk triage.
- Civic tech researchers reviewing public procurement patterns.
- Journalists or watchdog groups investigating government purchasing.
- Developers building local-first procurement workflows.

### Secondary users

- Government transparency teams.
- Auditors preparing leads for deeper review.
- Researchers testing procurement risk heuristics.

## 6. Core user journeys

### 6.1 Quick triage

A user runs:

```bash
probid probe "laptop"
```

They receive:

1. a summary of scanned records,
2. top reason-coded findings,
3. a risk map,
4. suggested next checks.

### 6.2 Evidence review

A user runs:

```bash
probid probe "laptop" --why
```

They receive evidence snippets, confidence, and caveats for each finding.

### 6.3 Automation/export

A user runs:

```bash
probid probe "laptop" --json
```

or uses the harness:

```bash
probid -q "probe laptop awards" --session-dir .probid-sessions --json-output
probid -q "make this a markdown report" --session-dir .probid-sessions --continue-recent --export-output --output report.md
```

They receive structured output suitable for downstream processing or analyst handoff.

### 6.4 Follow-up investigation

A user continues a persisted session:

```bash
probid -q "explain the top finding" --session-dir .probid-sessions --continue-recent --json-output
```

The harness uses prior session context to answer without fabricating missing evidence.

## 7. Functional requirements

### 7.1 CLI and harness

- `probid` opens the interactive terminal harness by default.
- `probid agent` opens the same harness explicitly.
- `probid -q <query>` runs one-shot harness mode.
- `probid probe <query>` is the primary direct command for procurement triage.
- Existing direct commands remain available, including:
  - `search`
  - `detail`
  - `awards`
  - `agency`
  - `supplier`
  - `overprice`
  - `repeat`
  - `network`
  - `split`
  - `exports`

### 7.2 Probe workflow

`probid probe` must support:

- required query keyword,
- optional agency filter,
- page limit,
- cache-only operation,
- `--why` evidence/caveat mode,
- `--json` machine-readable mode,
- confidence filtering,
- maximum findings cap.

Default text output should include:

1. Summary
2. Top findings
3. Risk map
4. Suggested next checks

### 7.3 Reason-coded findings

Probe findings should use the reason-code catalog:

- R1: Repeat supplier concentration
- R2: Near-ABC award pattern
- R3: Potential split contracts in short interval
- R4: Procurement mode outlier frequency
- R5: Abnormal budget-utilization spread for similar category
- R6: Single-agency dependence risk
- R7: Sparse/low-confidence data warning
- R8: Beneficial ownership disclosure gap when data exists, or explicit local data gap when unavailable

Each finding should include:

- reason code,
- human-readable summary,
- severity,
- confidence,
- evidence fields,
- caveats or false-positive notes,
- source references when available.

### 7.4 Local data and scraping

- Use SQLite as the local cache.
- Prefer cache reuse where possible.
- Scrape PhilGEPS only when needed and supported by the command mode.
- Handle PhilGEPS failures gracefully with explicit uncertainty.
- Do not fabricate missing fields.

### 7.5 Session and export workflows

The harness should support persisted session workflows:

- continue most recent session,
- explain prior findings,
- list prior exports,
- show last export destination or format,
- re-export the last artifact without rerunning tools.

Supported export outputs include:

- JSON content,
- Markdown report,
- CSV summary,
- case timeline,
- findings table,
- analyst handoff note.

Extension rules:

- `.json` for structured exports,
- `.md` / `.markdown` for markdown-style exports,
- `.csv` for CSV summaries,
- reject mismatched extensions with a clear error.

## 8. Non-functional requirements

### 8.1 Minimalism

- Keep the default experience small and terminal-first.
- Avoid new top-level commands unless necessary.
- Add depth through flags and follow-ups.

### 8.2 Explainability

- Every risk flag must be traceable to evidence fields.
- Outputs must distinguish risk signals from legal conclusions.
- Missing data and low confidence must be explicit.

### 8.3 Local-first operation

- Core workflows should work from the local SQLite cache where possible.
- Avoid paid dependencies and cloud-only designs.

### 8.4 Legal consistency

- Use RA 12009 + IRR semantics for procurement logic.
- Treat RA 9184-era assumptions as legacy unless explicitly requested.

### 8.5 Reliability

- Commands should fail gracefully with user-readable errors.
- Sparse datasets should not crash; they should produce R7-style data-quality warnings.
- JSON modes must emit parseable JSON without Rich formatting.

## 9. Data sources and constraints

Primary source:

- PhilGEPS notices site: <https://notices.philgeps.gov.ph/>

Known constraints:

- PhilGEPS is an ASP.NET WebForms site.
- Search mode may require a postback before stable selectors are available.
- Some fields, including budget, may appear only on detail pages.
- Scraping can be brittle; cache-first fallback and explicit caveats are required.

## 10. Success metrics

Near-term product success can be measured by:

- `probid probe "laptop"` returns useful summary-first output without extra setup after install.
- `probid probe "laptop" --json` emits valid parseable JSON.
- Sparse local data produces low-confidence warnings rather than crashes.
- Findings include evidence, confidence, and caveats.
- Existing commands remain backward compatible.
- Full active package test suite passes via `python scripts/run_tests.py`.

## 11. Manual acceptance checks

Before a v0.2-style release, validate:

1. `probid probe "laptop"` returns summary, findings, risk map, and next checks.
2. `probid probe "laptop" --why` includes evidence and caveats.
3. `probid probe "laptop" --json` is parseable by `python -m json.tool`.
4. `probid search "laptop"` behavior remains unchanged.
5. `probid detail <ref>` works with cached and forced modes where data exists.
6. `probid awards --cache-only` works.
7. At least one R-code appears on a realistic dataset when applicable.
8. Sparse datasets do not crash and produce an R7-style warning.
9. README documents probe-first usage and reason-code meanings.
10. AGENTS.md reflects current command and output expectations.
11. Export audit flow works: create export, show last export destination, list prior exports, and re-export last artifact.

## 12. Risks and mitigations

### Risk: signal inflation

Noisy heuristics may overstate risk.

Mitigation:

- Use confidence tiers.
- Include false-positive notes.
- Cap top findings by default.
- Avoid guilt language.

### Risk: scraping instability

PhilGEPS UI changes may break live data collection.

Mitigation:

- Prefer stable selectors.
- Use retry and graceful fallback.
- Reuse the local cache.
- Surface missing-data caveats.

### Risk: legal misinterpretation

Users may mistake risk flags for legal findings.

Mitigation:

- Use explicit language: risk signal, not verdict.
- Preserve source traceability.
- Include legal caveats in relevant outputs.

### Risk: CLI complexity creep

Too many commands or modes may undermine the minimal experience.

Mitigation:

- Keep `probe` as the primary front door.
- Keep advanced workflows optional.
- Add depth through flags and session follow-ups.

## 13. Current package architecture

- `packages/probing-agent/`: main CLI application and active product surface.
- `packages/agent/`: reusable agent runtime primitives.
- `packages/ai/`: AI client/provider integration layer.
- `packages/tui/`: terminal UI primitives.
- `packages/web-ui/`: experimental browser UI rendering package.

Main entrypoints:

- CLI: `packages/probing-agent/src/probid_probing_agent/cli.py`
- Commands: `packages/probing-agent/src/probid_probing_agent/cli/`
- Runtime: `packages/probing-agent/src/probid_probing_agent/core/`
- Interactive mode: `packages/probing-agent/src/probid_probing_agent/modes/interactive/`
- Heuristics: `packages/probing-agent/src/probid_probing_agent/core/analysis/detectors.py`
- PhilGEPS source: `packages/probing-agent/src/probid_probing_agent/core/sources/philgeps.py`
- SQLite cache: `packages/probing-agent/src/probid_probing_agent/core/data/cache.py`

## 14. Roadmap direction

### v0.2 theme

Signal-first minimal workflow with progressive disclosure:

- summary-first outputs,
- evidence-rich detail on demand,
- reason-coded flags,
- confidence and caveats,
- JSON/export support.

### Future considerations

- Improve cache inspection and data-quality diagnostics.
- Expand heuristics only when evidence fields and false-positive notes are clear.
- Strengthen session handoff and export audit flows.
- Keep web UI experimental unless a strong user need emerges.
