"""Shared API schemas (pagination, messages)."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


class MessageResponse(BaseModel):
    success: bool = True
    message: str


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total_items: int
    total_pages: int


class PaginationParams(BaseModel):
    page: int = Field(default=DEFAULT_PAGE, ge=1)
    page_size: int = Field(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)


def normalize_pagination(page: int, page_size: int) -> tuple[int, int, int]:
    """Return (page, page_size, offset)."""
    safe_page = max(1, page)
    safe_size = min(max(1, page_size), MAX_PAGE_SIZE)
    offset = (safe_page - 1) * safe_size
    return safe_page, safe_size, offset


def build_paginated_response(
    *,
    items: list[T],
    page: int,
    page_size: int,
    total_items: int,
) -> PaginatedResponse[T]:
    total_pages = (total_items + page_size - 1) // page_size if page_size else 0
    return PaginatedResponse(
        items=items,
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )
