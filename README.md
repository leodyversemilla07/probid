# probid

Probe Philippine government procurement.

Minimal tool. Serious purpose.

- Local-first procurement scrutiny
- Explainable risk flags (not verdicts)
- RA 12009 + IRR baseline

See `AGENTS.md` for agent-specific project guidance.

`probid` helps you search PhilGEPS notices, inspect notice details, review contract awards, and run simple heuristics for suspicious procurement patterns.

Data source: [PhilGEPS](https://notices.philgeps.gov.ph/) (Philippine Government Electronic Procurement System).

## Features

- Probe data with summary-first, reason-coded findings (`probe`)
- Search procurement notices by keyword
- Fetch full notice details by reference number
- View recent contract awards
- Inspect supplier and agency activity from the local cache
- Detect possible overpricing, repeat awardees, supplier networks, and contract splitting
- Reuse a local SQLite cache to reduce scraping

## Install

```bash
pip install -e .
playwright install chromium
```

## Usage

```bash
# Probe procurement data (summary-first)
probid probe "laptop"

# Probe with explainers (evidence + caveats)
probid probe "laptop" --why

# Probe as machine-readable JSON
probid probe "laptop" --json

# Search procurement notices
probid search "laptop"
probid search "server" --pages 3 --detail

# Fetch a specific notice
probid detail 12905086

# List contract awards
probid awards
probid awards --agency "DICT" --supplier "ACME"

# Supplier profile
probid supplier "ACME CORPORATION"

# Agency profile
probid agency "DICT"

# Detect overpricing
probid overprice "laptop" --threshold 150

# Find repeat awardees
probid repeat --min-count 3

# Supplier network analysis
probid network "ACME CORPORATION"

# Detect contract splitting
probid split "DICT" --gap-days 30

# List all agencies
probid agencies
```

Tip: use `--cache-only` on `probe`, `search`, and `awards` to query the local SQLite cache without scraping.

## Reason codes

`probe` findings use reason codes for explainability:

- R1: Repeat supplier concentration
- R2: Near-ABC award pattern
- R3: Potential split contracts in short interval
- R4: Procurement mode outlier frequency (excluding unknown mode labels)
- R5: Abnormal budget-utilization spread for similar category
- R6: Single-agency dependence risk (supplier)
- R7: Sparse/low-confidence data warning
- R8: Beneficial ownership disclosure gap (data unavailable locally)

`probe` summary also includes a data-quality gate:
- `adequate`: enough local volume for initial triage signal
- `limited`: use wider query/pages for stronger confidence
- `constrained`: very sparse local data; findings are low-confidence

## Project structure

The repo name remains `probid`, and the installed CLI command is still `probid`, but the internal Python package is now `app`.

```text
probid
├── README.md
├── pyproject.toml
└── src
    └── app
        ├── __init__.py
        ├── cli.py
        ├── commands
        │   ├── analysis.py
        │   ├── awards.py
        │   ├── profiles.py
        │   └── search.py
        ├── data
        │   ├── cache.py
        │   └── models.py
        ├── analysis
        │   └── detectors.py
        ├── sources
        │   └── philgeps.py
        └── ui
            └── display.py
```

## How the project works

```mermaid
flowchart TD
    User["User runs probid command"] --> CLI["CLI entrypoint\nsrc/app/cli.py"]
    CLI --> Commands["Command handlers\nsrc/app/commands/*"]

    Commands -->|fetch live data| Source["PhilGEPS scraper\nsrc/app/sources/philgeps.py"]
    Commands -->|read/write local data| Cache["SQLite cache\nsrc/app/data/cache.py"]
    Commands -->|run heuristics| Detectors["Analysis engine\nsrc/app/analysis/detectors.py"]
    Commands -->|render output| UI["Terminal display\nsrc/app/ui/display.py"]

    Source --> Cache
    Cache --> Detectors
    Detectors --> UI
    Cache --> UI
```

### Responsibilities

- `src/app/cli.py` — thin Click entrypoint
- `src/app/commands/` — CLI commands grouped by feature
- `src/app/data/` — cache access and typed models
- `src/app/analysis/` — anomaly detection and analysis logic
- `src/app/sources/` — external data connectors and scrapers
- `src/app/ui/` — Rich terminal rendering

## Cache

Data is stored locally at:

```text
~/.probid/probid.db
```

Override the cache directory with:

```bash
export PROBID_CACHE_DIR=/path/to/cache-dir
```

## License

MIT
