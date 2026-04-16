# @probid/ai

AI provider client layer for probid.

Status: **extracted** — provides typed client abstractions for AI API calls.

## Features

- **BaseAIClient** — abstract base for AI provider clients
- **OpenAIClient** — OpenAI-compatible client (works with OpenAI, Anthropic via adapter, etc.)
- **Typed request/response** — `ChatCompletionRequest`, `ChatCompletionResponse`, `Message`, `StreamChunk`
- **Streaming support** — `chat_completions_stream()` generator
- **Provider key resolver** — `get_env_api_key(provider)` with pi-style env precedence rules
- **API provider registry** — register/get/unregister stream handlers by API
- **Model helpers** — `get_model`, `get_models`, `get_providers`, `calculate_cost`, `supports_xhigh`

## Usage

```python
from probid_ai.types import ChatCompletionRequest, Message
from probid_ai.openai_client import OpenAIClient

client = OpenAIClient()  # uses OPENAI_API_KEY env var

request = ChatCompletionRequest(
    model="gpt-4",
    messages=[
        Message(role="system", content="You are a helpful assistant."),
        Message(role="user", content="What is probid?"),
    ],
    temperature=0.7,
)

response = client.chat_completions(request)
print(response.choices[0].message.content)
```

## Environment variables

`OpenAIClient` still uses `OPENAI_API_KEY`/`OPENAI_BASE_URL` by default, and the package now also exposes `get_env_api_key(provider)` for cross-provider env-key discovery (e.g. `anthropic`, `openrouter`, `google-vertex`, `amazon-bedrock`, `github-copilot`).

## Testing

```bash
python3 -m unittest packages/ai/tests -v
```
