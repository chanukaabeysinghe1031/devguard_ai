"""HTML → clean Markdown for official documentation pages.

Strips navigation, scripts, footers, and cookie chrome. Keeps headings,
paragraphs, lists, tables, and fenced code blocks.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any


_SKIP_TAGS = frozenset(
    {
        "script",
        "style",
        "noscript",
        "svg",
        "nav",
        "footer",
        "header",
        "aside",
        "form",
        "iframe",
        "button",
        "template",
    }
)
_BLOCK_TAGS = frozenset({"p", "div", "section", "article", "main", "li", "tr", "blockquote"})
_HEADING_TAGS = {f"h{i}": i for i in range(1, 7)}
_CONTENT_ID_HINTS = (
    "main-col-body",
    "awsdocs-content",
    "main-content",
    "main-column",
    "content-body",
    "page-content",
    "docs-content",
    "article-body",
    "main",
    "content",
)


def _looks_like_chrome(tag: str, classes: str) -> bool:
    needles = (
        "cookie",
        "consent",
        "navbar",
        "nav-bar",
        "breadcrumb",
        "sidebar",
        "left-nav",
        "right-rail",
        "advert",
        "promo",
        "newsletter",
        "cookie-banner",
    )
    return any(n in classes for n in needles)


class _HtmlToMarkdown(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_stack: list[str] = []
        self._in_pre = 0
        self._in_code = 0
        self._list_stack: list[str] = []
        self._link_depth = 0
        self._pending_href: str | None = None
        self._title: str | None = None
        self._in_title = False

    @property
    def _skip_depth(self) -> int:
        return len(self._skip_stack)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attr = {k.lower(): (v or "") for k, v in attrs}
        classes = f"{attr.get('class', '')} {attr.get('id', '')}".lower()

        if tag == "title":
            self._in_title = True
            return
        if self._skip_depth or tag in _SKIP_TAGS or _looks_like_chrome(tag, classes):
            self._skip_stack.append(tag)
            return

        if tag in _HEADING_TAGS:
            level = _HEADING_TAGS[tag]
            self._parts.append("\n\n" + ("#" * level) + " ")
            return
        if tag == "p":
            self._parts.append("\n\n")
            return
        if tag == "br":
            self._parts.append("\n")
            return
        if tag == "hr":
            self._parts.append("\n\n---\n\n")
            return
        if tag in {"ul", "ol"}:
            self._list_stack.append(tag)
            self._parts.append("\n")
            return
        if tag == "li":
            bullet = "1." if self._list_stack and self._list_stack[-1] == "ol" else "-"
            indent = "  " * max(0, len(self._list_stack) - 1)
            self._parts.append(f"\n{indent}{bullet} ")
            return
        if tag == "pre":
            self._in_pre += 1
            self._parts.append("\n\n```\n")
            return
        if tag == "code" and self._in_pre == 0:
            self._in_code += 1
            self._parts.append("`")
            return
        if tag == "table":
            self._parts.append("\n\n")
            return
        if tag == "tr":
            self._parts.append("\n| ")
            return
        if tag == "a":
            href = attr.get("href")
            if href and not href.startswith(("#", "javascript:")):
                self._pending_href = href
                self._link_depth += 1
                self._parts.append("[")
            return
        if tag in {"strong", "b"}:
            self._parts.append("**")
            return
        if tag in {"em", "i"}:
            self._parts.append("*")
            return

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
            return
        if self._skip_stack:
            # Pop the nearest matching open skip tag; if missing, pop one level.
            if tag in self._skip_stack:
                while self._skip_stack:
                    opened = self._skip_stack.pop()
                    if opened == tag:
                        break
            else:
                self._skip_stack.pop()
            return
        if tag == "pre":
            if self._in_pre:
                self._in_pre -= 1
            self._parts.append("\n```\n\n")
            return
        if tag == "code" and self._in_pre == 0 and self._in_code:
            self._in_code -= 1
            self._parts.append("`")
            return
        if tag in {"ul", "ol"} and self._list_stack:
            self._list_stack.pop()
            self._parts.append("\n")
            return
        if tag == "table":
            self._parts.append("\n\n")
            return
        if tag == "tr":
            self._parts.append("|")
            return
        if tag in {"th", "td"}:
            self._parts.append(" | ")
            return
        if tag == "a" and self._link_depth:
            self._link_depth -= 1
            href = self._pending_href or ""
            self._pending_href = None
            self._parts.append(f"]({href})" if href else "]")
            return
        if tag in {"strong", "b"}:
            self._parts.append("**")
            return
        if tag in {"em", "i"}:
            self._parts.append("*")
            return
        if tag in _BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title:
            text = data.strip()
            if text and not self._title:
                self._title = text
            return
        if self._skip_depth:
            return
        if self._in_pre:
            self._parts.append(data)
            return
        text = re.sub(r"[ \t]+", " ", data)
        if not text.strip():
            return
        self._parts.append(text)

    def markdown(self) -> str:
        raw = "".join(self._parts)
        raw = raw.replace("\r\n", "\n")
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        raw = re.sub(r"[ \t]+\n", "\n", raw)
        return raw.strip()


def _strip_noisy_tags(html: str) -> str:
    cleaned = re.sub(r"(?is)<script\b[^>]*>.*?</script>", "", html)
    cleaned = re.sub(r"(?is)<style\b[^>]*>.*?</style>", "", cleaned)
    cleaned = re.sub(r"(?is)<noscript\b[^>]*>.*?</noscript>", "", cleaned)
    cleaned = re.sub(r"(?is)<svg\b[^>]*>.*?</svg>", "", cleaned)
    cleaned = re.sub(r"(?is)<!--.*?-->", "", cleaned)
    return cleaned


def _extract_by_id(html: str, element_id: str) -> str | None:
    pattern = re.compile(
        rf'(?is)<([a-z0-9]+)([^>]*\bid=["\']{re.escape(element_id)}["\'][^>]*)>(.*)$'
    )
    match = pattern.search(html)
    if not match:
        return None
    tag = match.group(1).lower()
    rest = match.group(3)
    # Walk until the matching close tag at depth 0.
    depth = 1
    idx = 0
    token = re.compile(rf"(?is)</?{tag}\b[^>]*>")
    for tok in token.finditer(rest):
        token_text = tok.group(0)
        if token_text.startswith("</"):
            depth -= 1
            if depth == 0:
                idx = tok.end()
                break
        elif not token_text.endswith("/>"):
            depth += 1
    if idx <= 0:
        return None
    return rest[: idx - len(f"</{tag}>")]


def _largest_content_region(html: str) -> str:
    candidates: list[str] = []
    for element_id in _CONTENT_ID_HINTS:
        region = _extract_by_id(html, element_id)
        if region and len(region.strip()) > 80:
            candidates.append(region)
    for tag in ("main", "article"):
        match = re.search(rf"(?is)<{tag}\b[^>]*>(.*?)</{tag}>", html)
        if match and len(match.group(1).strip()) > 80:
            candidates.append(match.group(1))
    if candidates:
        return max(candidates, key=len)
    body = re.search(r"(?is)<body\b[^>]*>(.*?)</body>", html)
    return body.group(1) if body else html


def _plaintext_fallback(html: str) -> str:
    text = re.sub(r"(?is)<br\s*/?>", "\n", html)
    text = re.sub(r"(?is)</p>", "\n\n", text)
    text = re.sub(r"(?is)</h([1-6])>", "\n\n", text)
    text = re.sub(r"(?is)<h([1-6])\b[^>]*>", lambda m: "\n\n" + ("#" * int(m.group(1))) + " ", text)
    text = re.sub(r"(?is)<li\b[^>]*>", "\n- ", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def html_to_markdown(html: str) -> dict[str, Any]:
    """Parse HTML into clean Markdown plus extracted title."""
    cleaned = _strip_noisy_tags(html)
    title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", cleaned)
    title = re.sub(r"\s+", " ", title_match.group(1)).strip() if title_match else None

    region = _largest_content_region(cleaned)
    parser = _HtmlToMarkdown()
    try:
        parser.feed(region)
        parser.close()
    except Exception:  # noqa: BLE001
        markdown = _plaintext_fallback(region)
        return {
            "title": title,
            "markdown": markdown,
            "headings": [
                {"level": len(m.group(1)), "text": m.group(2).strip()}
                for m in re.finditer(r"^(#{1,6})\s+(.+)$", markdown, flags=re.M)
            ],
        }

    markdown = parser.markdown()
    if title and not parser._title:
        parser._title = title
    if len(markdown) < 80:
        markdown = _plaintext_fallback(region)
    if len(markdown) < 80:
        markdown = _plaintext_fallback(cleaned)

    headings = [
        {"level": len(hashes), "text": text.strip()}
        for hashes, text in re.findall(r"^(#{1,6})\s+(.+)$", markdown, flags=re.M)
    ]
    return {
        "title": parser._title or title,
        "markdown": markdown,
        "headings": headings,
    }


def extract_heading_hierarchy(markdown: str) -> list[str]:
    return [m.group(2).strip() for m in re.finditer(r"^(#{1,6})\s+(.+)$", markdown, flags=re.M)]
