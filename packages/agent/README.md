# @probid/agent-core

Core agent runtime primitives for probid.

Status: extracted and tested.

## Extracted pieces

- `probid_agent.agent.ToolRegistry` + `ToolSpec`
- `probid_agent.agent_loop.BaseAgentSession`
- `probid_agent.provider_registry.Provider`, `register_provider`, `require_provider`, `list_providers`
- `probid_agent.session_manager.JsonlSessionManager`
- `probid_agent.session_logger.JsonlTurnLogger`
- `probid_agent.proxy.validate_plan_contract`, `execute_plan_steps`, `run_plan_execution`
- `probid_agent.runtime_base.BaseAgentRuntime`
- `probid_agent.response_composer.BaseResponseComposer` with `DomainResponsePolicy` support
- `probid_agent.runtime_lifecycle.open_or_create_session`, `persist_turn`, `restore_turn_messages`
- `probid_agent.errors.PlanValidationError`, `ProviderRegistryError`
- shared runtime contracts in `probid_agent.types` (`ExecutionPlan`, `ToolTraceItem`, `ResponseEnvelope`, `PlanExecutionResult`, `SessionProtocol`, `RuntimeStateProtocol`, `DomainResponsePolicy`, provider protocol)

## Quick usage

```python
from probid_agent.provider_registry import Provider, register_provider, require_provider
from probid_agent.session_manager import JsonlSessionManager
from probid_agent.proxy import validate_plan_contract, execute_plan_steps
from pathlib import Path

# Register a provider
def my_handler(input_text, runtime):
    return {"result": f"processed: {input_text}"}

register_provider(Provider(name="test", handle=my_handler))

# Validate a plan
plan = {"steps": [{"tool": "probe", "args": {}, "cli_equivalent": "probid probe x"}]}
validate_plan_contract(plan)  # passes

# Execute plan steps with a mock registry
class MockRegistry:
    def execute(self, name, args, cli_equivalent="", event_sink=None):
        return {"ok": True}, {"tool": name, "status": "success"}

payload, trace = execute_plan_steps(plan, MockRegistry())
print(payload)  # {"ok": True}
```

## Testing

```bash
python3 -m unittest packages/agent/tests -v
```
