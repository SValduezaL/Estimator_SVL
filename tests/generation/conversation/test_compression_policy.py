from __future__ import annotations

from app.generation.conversation.compression.compression_policy import CompressionPolicy
from app.generation.conversation.models import AnchorItem, Message


def test_compression_policy_excludes_anchor_messages() -> None:
    removed = [
        Message(role="user", content="Debe cumplir ISO 27001"),
        Message(role="assistant", content="Anotado"),
        Message(role="user", content="Quiero roadmap en 3 fases"),
    ]
    anchors = [AnchorItem(topic="compliance", fact="Debe cumplir ISO 27001")]
    compressible = CompressionPolicy.apply(removed_messages=removed, anchors=anchors)
    contents = [m.content for m in compressible]
    assert "Debe cumplir ISO 27001" not in contents
    assert "Quiero roadmap en 3 fases" in contents
