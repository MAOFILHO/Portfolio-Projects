"""What the relay needs from a media transport.

Structural, not inherited: FastAPI's WebSocket already satisfies this without knowing the
protocol exists, and so does the FakeTransport beside it. Stating it explicitly is what lets
`run_call` take either one and lets a reader see, in one place, exactly how much of a WebSocket
the relay actually depends on -- two methods.
"""
from typing import Protocol


class MediaTransport(Protocol):
    """One caller's media stream. Text frames carrying base64 PCM, per ACS's wire format."""

    async def receive_text(self) -> str:
        """Next inbound frame. Raises WebSocketDisconnect when the caller hangs up."""
        ...

    async def send_text(self, text: str) -> None:
        """Send one outbound frame."""
        ...
