.PHONY: test test-contract help run

PYTHONPATH_MONOREPO=packages/probing-agent/src:packages/agent/src:packages/ai/src:packages/tui/src:packages/mom/src:packages/pods/src

test:
	python3 scripts/run_tests.py

test-contract:
	PYTHONPATH=$(PYTHONPATH_MONOREPO) python3 -m unittest packages/probing-agent/tests/test_probe_output_contract.py -v

help:
	PYTHONPATH=$(PYTHONPATH_MONOREPO) python3 -m probid_probing_agent.main --help

run:
	PYTHONPATH=$(PYTHONPATH_MONOREPO) python3 -m probid_probing_agent.main
