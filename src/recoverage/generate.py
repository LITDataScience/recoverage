"""Planned test files. The sandbox in assure.py decides what gets copied back."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PlannedTest:
    path: str
    content: str
    action: str
