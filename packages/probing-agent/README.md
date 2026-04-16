# @probid/probing-agent

Interactive probing agent CLI for probid.

## Runtime notes

- Uses shared `agent-core` primitives from `packages/agent`.
- Applies procurement-specific response behavior via:
  - `core/response_policy.py` (`ProcurementResponsePolicy`)
  - `core/response_builder.py` (`ResponseBuilder`)
- Generic response composition stays in `probid_agent.response_composer.BaseResponseComposer`.
