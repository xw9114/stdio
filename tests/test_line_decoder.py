from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from app.core.process_manager import IncrementalLineDecoder


def _feed_bytewise(decoder: IncrementalLineDecoder, data: bytes) -> list[str]:
    lines: list[str] = []
    for index in range(len(data)):
        lines.extend(decoder.feed(data[index : index + 1]))
    return lines


def test_multibyte_character_split_across_chunks_is_not_corrupted() -> None:
    """Regression test: each chunk used to be decoded on its own, so a CJK
    character (3 bytes in UTF-8) straddling a chunk boundary came out as
    U+FFFD replacement characters."""
    encoded = "Brain 正在分析任务\n".encode("utf-8")
    split_at = encoded.index("正".encode("utf-8")) + 1  # inside the character
    decoder = IncrementalLineDecoder()

    lines = decoder.feed(encoded[:split_at]) + decoder.feed(encoded[split_at:])

    assert lines == ["Brain 正在分析任务"]
    assert decoder.flush() == []


def test_byte_by_byte_feed_yields_identical_lines() -> None:
    text = "第一行\r\n第二行\n第三行\r\n"
    decoder = IncrementalLineDecoder()

    lines = _feed_bytewise(decoder, text.encode("utf-8")) + decoder.flush()

    assert lines == ["第一行", "第二行", "第三行"]


def test_crlf_split_across_chunks_does_not_emit_blank_line() -> None:
    decoder = IncrementalLineDecoder()

    lines = decoder.feed(b"step one\r") + decoder.feed(b"\nstep two\r\n")

    assert lines == ["step one", "step two"]


def test_lone_carriage_return_still_separates_lines() -> None:
    decoder = IncrementalLineDecoder()

    lines = decoder.feed(b"progress 10%\rprogress 20%\r") + decoder.feed(b"done\n")

    assert lines == ["progress 10%", "progress 20%", "done"]


def test_flush_emits_unterminated_tail() -> None:
    decoder = IncrementalLineDecoder()

    assert decoder.feed(b"complete line\npartial") == ["complete line"]
    assert decoder.flush() == ["partial"]
    assert decoder.flush() == []


def test_flush_replaces_truncated_multibyte_sequence() -> None:
    decoder = IncrementalLineDecoder()

    assert decoder.feed("结束".encode("utf-8")[:4]) == []
    assert decoder.flush() == ["结�"]


def test_empty_lines_are_preserved() -> None:
    decoder = IncrementalLineDecoder()

    assert decoder.feed(b"a\n\nb\n") == ["a", "", "b"]
