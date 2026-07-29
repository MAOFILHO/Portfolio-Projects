"""Test double for semantic_kernel.Kernel -- just enough surface for the
agents in shared/surveil_core/agents to construct and run against, without
ever calling a real Azure OpenAI endpoint.
"""

from __future__ import annotations


class FakeChatResponse:
    def __init__(self, text: str) -> None:
        self._text = text

    def __str__(self) -> str:
        return self._text


class FakeChatService:
    def __init__(self, response_text: str) -> None:
        self.response_text = response_text
        self.calls: list[tuple] = []
        self.ai_model_id = "fake-model"

    async def get_chat_message_content(self, history, settings, **kwargs):
        self.calls.append((history, settings, kwargs))
        return FakeChatResponse(self.response_text)


class FakeKernel:
    """Stand-in for `semantic_kernel.Kernel`. `get_service()` returns a
    `FakeChatService` regardless of the requested type; `add_plugin()` just
    records what was registered.
    """

    def __init__(self, response_text: str = "{}") -> None:
        self.service = FakeChatService(response_text)
        self.plugins: dict[str, object] = {}

    def get_service(self, service_id=None, type=None):
        return self.service

    def add_plugin(self, plugin, plugin_name=None, **kwargs):
        self.plugins[plugin_name] = plugin
        return plugin
