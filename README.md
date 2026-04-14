# probid

Probe Philippine government procurement. Search bids, track awards, detect suspicious patterns.

Data sourced from [PhilGEPS](https://notices.philgeps.gov.ph/) (Philippine Government Electronic Procurement System).

## Install

```bash
pip install -e .
playwright install chromium
```

## Usage

```bash
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

# Find repeat awardees (potential red flags)
probid repeat --min-count 3

# Supplier network analysis
probid network "ACME CORPORATION"

# Detect contract splitting
probid split "DICT" --gap-days 30

# List all agencies
probid agencies
```

Use `--cache-only` on search/awards to query the local SQLite cache without scraping.

## Architecture

```
src/
  probid/
    sources/
      philgeps.py    # Playwright scraper for PhilGEPS
    cache.py         # SQLite-backed local cache
    analyze.py       # Overpricing, repeat awardees, contract splitting detection
    models.py        # Data classes (reference types)
    display.py       # Rich terminal output
    cli.py           # Click CLI entry point
```

Data is cached at `~/.probid/probid.db`. Override with `PROBID_CACHE_DIR` env var.

## License

MIT
