"""AI provider client layer for probid."""

from probid_ai.api_registry import (
    ApiProvider,
    clear_api_providers,
    get_api_provider,
    get_api_providers,
    register_api_provider,
    unregister_api_providers,
)
from probid_ai.client import APIError, BaseAIClient, getenv_or_raise
from probid_ai.env_api_keys import get_env_api_key
from probid_ai.models import (
    calculate_cost,
    get_model,
    get_models,
    get_providers,
    models_are_equal,
    supports_xhigh,
)
from probid_ai.openai_client import OpenAIClient
from probid_ai.types import (
    Api,
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Message,
    Model,
    Provider,
    StreamChunk,
)

__all__ = [
    "APIError",
    "Api",
    "ApiProvider",
    "BaseAIClient",
    "OpenAIClient",
    "Provider",
    "Model",
    "register_api_provider",
    "get_api_provider",
    "get_api_providers",
    "unregister_api_providers",
    "clear_api_providers",
    "get_model",
    "get_models",
    "get_providers",
    "calculate_cost",
    "supports_xhigh",
    "models_are_equal",
    "getenv_or_raise",
    "get_env_api_key",
    "ChatCompletionRequest",
    "ChatCompletionResponse",
    "Message",
    "ChatCompletionChoice",
    "StreamChunk",
]
