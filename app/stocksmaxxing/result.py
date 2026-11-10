"""Lightweight Result type for stocksmaxxing adapters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Ok[T]:
    value: T


@dataclass(frozen=True)
class Err:
    code: str
    message: str
    hint: str | None = None


type Result[T] = Ok[T] | Err


def is_ok[T](result: Result[T]) -> bool:
    return isinstance(result, Ok)
