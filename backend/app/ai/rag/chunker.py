"""Chunk markdown knowledge documents for RAG ingestion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    index: int
    heading: str | None
    content: str
    token_count: int


def chunk_markdown(text: str, *, max_chars: int = 900) -> list[TextChunk]:
    """Split markdown into heading-aware chunks sized for embedding."""
    lines = text.replace("\r\n", "\n").split("\n")
    sections: list[tuple[str | None, list[str]]] = []
    current_heading: str | None = None
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        body = "\n".join(buffer).strip()
        if body:
            sections.append((current_heading, buffer[:]))
        buffer = []

    for line in lines:
        if line.startswith("#"):
            flush()
            current_heading = line.lstrip("#").strip() or None
            buffer = [line]
        else:
            buffer.append(line)
    flush()

    chunks: list[TextChunk] = []
    index = 0
    for heading, section_lines in sections:
        content = "\n".join(section_lines).strip()
        if not content:
            continue
        if len(content) <= max_chars:
            chunks.append(
                TextChunk(
                    index=index,
                    heading=heading,
                    content=content,
                    token_count=max(1, len(content.split())),
                )
            )
            index += 1
            continue
        # Hard-split oversized sections.
        start = 0
        while start < len(content):
            piece = content[start : start + max_chars].strip()
            if piece:
                chunks.append(
                    TextChunk(
                        index=index,
                        heading=heading,
                        content=piece,
                        token_count=max(1, len(piece.split())),
                    )
                )
                index += 1
            start += max_chars
    return chunks
