from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Generic, TypeVar


DEFAULT_PER_PAGE = 15
MAX_PER_PAGE = 100

T = TypeVar("T")


def sanitize_page(value: str | int | None) -> int:
    try:
        page = int(value or 1)
    except (TypeError, ValueError):
        return 1
    return max(page, 1)


def sanitize_per_page(value: str | int | None, *, default: int = DEFAULT_PER_PAGE) -> int:
    try:
        per_page = int(value or default)
    except (TypeError, ValueError):
        return default
    return max(1, min(per_page, MAX_PER_PAGE))


@dataclass
class PaginationResult(Generic[T]):
    items: list[T]
    page: int
    per_page: int
    total: int

    @property
    def total_pages(self) -> int:
        if self.total <= 0:
            return 1
        return ceil(self.total / self.per_page)

    @property
    def has_prev(self) -> bool:
        return self.page > 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def start_item(self) -> int:
        if self.total <= 0:
            return 0
        return ((self.page - 1) * self.per_page) + 1

    @property
    def end_item(self) -> int:
        if self.total <= 0:
            return 0
        return min(self.page * self.per_page, self.total)
