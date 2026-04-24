.PHONY: test test-contract help run sync lint format check type

PYTHONPATH_MONOREPO=packages/probing-agent/src:packages/agent/src:packages/ai/src:packages/tui/src:packages/mom/src:packages/pods/src

sync:
	uv sync --extra dev

type:
	uv run ty check

lint:
	uv run ruff check packages/

format:
	uv run ruff format packages/

check: type
	uv run ruff check packages/
	uv run ruff format --check packages/

test:
	uv run python3 scripts/run_tests.py

test-contract:
	uv run python3 -m unittest packages/probing-agent/tests/test_probe_output_contract.py -v

help:
	uv run probid --help

run:
	uv run probid
