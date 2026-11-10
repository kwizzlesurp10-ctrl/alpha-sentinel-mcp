"""Lightweight Result type for stocksmaxxing adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T


@dataclass(frozen=True)
class Err:
    code: str
    message: str
    hint: str | None = None


Result = Ok[T] | Err


def is_ok(result: Result[T]) -> bool:
    return isinstance(result, Ok)
