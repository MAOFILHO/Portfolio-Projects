"""Builds a Semantic Kernel `Kernel` wired to Azure OpenAI via RBAC.

Matches this repo's existing no-keys stance for every other Azure client
(`_credential()` in the Function, `get_credential()` in the backend): the
chat completion connector authenticates with a bearer token derived from the
caller's `TokenCredential`, never an API key.
"""

from __future__ import annotations

from azure.core.credentials import TokenCredential
from azure.identity import get_bearer_token_provider
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion

from .tracing import configure_langfuse_tracing

_COGNITIVE_SERVICES_SCOPE = "https://cognitiveservices.azure.com/.default"


def build_kernel(endpoint: str, deployment_name: str, credential: TokenCredential) -> Kernel:
    configure_langfuse_tracing()
    kernel = Kernel()
    token_provider = get_bearer_token_provider(credential, _COGNITIVE_SERVICES_SCOPE)
    kernel.add_service(
        AzureChatCompletion(
            deployment_name=deployment_name,
            endpoint=endpoint,
            ad_token_provider=token_provider,
        )
    )
    return kernel


def get_chat_service(kernel: Kernel) -> AzureChatCompletion:
    return kernel.get_service(type=AzureChatCompletion)
