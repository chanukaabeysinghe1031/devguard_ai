"""Chunk markdown knowledge documents for RAG ingestion."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextChunk:
    index: int
    heading: str | None
    content: str
    token_count: int


def chunk_markdown(
    text: str,
    *,
    max_chars: int = 900,
    overlap: int = 0,
) -> list[TextChunk]:
    """Split markdown into heading-aware chunks sized for embedding.

    Prefer keeping fenced code, tables, and list blocks intact when a section
    fits under ``max_chars``. Oversized sections hard-split on paragraph
    boundaries when possible. ``overlap`` applies only to hard-splits (default 0
    preserves historical behaviour).
    """
    if max_chars < 200:
        raise ValueError("max_chars must be >= 200")
    if overlap < 0 or overlap >= max_chars:
        raise ValueError("overlap must be >= 0 and < max_chars")

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
        # Hard-split oversized sections on paragraph boundaries when possible.
        start = 0
        step = max(1, max_chars - overlap)
        while start < len(content):
            end = min(len(content), start + max_chars)
            if end < len(content):
                window = content[start:end]
                # Prefer not cutting inside fenced code.
                fence_count = window.count("```")
                if fence_count % 2 == 1:
                    next_fence = content.find("```", end)
                    if next_fence != -1 and next_fence - start <= max_chars + 400:
                        end = next_fence + 3
                else:
                    break_at = window.rfind("\n\n")
                    if break_at >= max_chars // 3:
                        end = start + break_at
            piece = content[start:end].strip()
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
            if end >= len(content):
                break
            start = max(end - overlap, start + step) if overlap else end
    return chunks
