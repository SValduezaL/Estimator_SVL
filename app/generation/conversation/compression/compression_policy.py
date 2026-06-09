"""Política de compresión para resumen acumulativo."""

from __future__ import annotations

from app.memory.models import AnchorItem, Message


class CompressionPolicy:
    """Activa compresión solo con mensajes eliminados que no sean anclas."""

    @staticmethod
    def apply(
        *,
        removed_messages: list[Message],
        anchors: list[AnchorItem],
    ) -> list[Message]:
        if not removed_messages:
            return []
        anchor_facts = {a.fact for a in anchors if a.status == "active"}
        compressible: list[Message] = []
        for message in removed_messages:
            if any(fact in message.content for fact in anchor_facts):
                continue
            compressible.append(message)
        return compressible
