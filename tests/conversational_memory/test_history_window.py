"""Tests de ventana deslizante del historial."""

from __future__ import annotations

from app.memory.models import Message
from app.memory.service import apply_sliding_window


def _turn(user: str, assistant: str) -> list[Message]:
    return [
        Message(role="user", content=user),
        Message(role="assistant", content=assistant),
    ]


def test_sliding_window_keeps_last_n_turns() -> None:
    history: list[Message] = []
    for i in range(8):
        history.extend(_turn(f"user-{i}", f"assistant-{i}"))

    truncated = apply_sliding_window(history, max_turns=6)

    assert len(truncated) == 12
    assert truncated[0].content == "user-2"
    assert truncated[-1].content == "assistant-7"


def test_sliding_window_preserves_chronological_order() -> None:
    history = _turn("a", "b") + _turn("c", "d") + _turn("e", "f")
    truncated = apply_sliding_window(history, max_turns=2)

    assert [m.content for m in truncated] == ["c", "d", "e", "f"]


def test_sliding_window_no_op_when_under_limit() -> None:
    history = _turn("only", "pair")
    truncated = apply_sliding_window(history, max_turns=6)
    assert truncated == history
