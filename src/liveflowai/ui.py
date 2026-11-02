"""Small, dependency-free presentation layer for the LiveFlowAI terminal app."""

from __future__ import annotations

import os
import shutil
import sys
from typing import Iterable, Sequence


class ConsoleUI:
    """Render a calm, readable interface while remaining usable in plain logs."""

    _enabled = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

    def _style(self, value: str, *codes: int) -> str:
        if not self._enabled:
            return value
        return f"\033[{';'.join(map(str, codes))}m{value}\033[0m"

    def _line(self, char: str = "─") -> str:
        return char * min(shutil.get_terminal_size((86, 24)).columns, 86)

    def header(self, eyebrow: str, title: str, subtitle: str = "") -> None:
        print()
        print(self._style(self._line(), 36))
        print(self._style(eyebrow.upper(), 36, 1))
        print(self._style(title, 1))
        if subtitle:
            print(self._style(subtitle, 2))
        print(self._style(self._line(), 36))

    def status(self, message: str, kind: str = "info") -> None:
        labels = {
            "info": ("INFO", 36),
            "success": ("DONE", 32),
            "warning": ("NOTE", 33),
            "error": ("ERROR", 31),
        }
        label, color = labels[kind]
        print(f"{self._style(f' {label} ', color, 1)} {message}")

    def menu(self, options: Sequence[tuple[str, str, str]]) -> None:
        for key, title, description in options:
            print(f"  {self._style(f'[{key}]', 36, 1)} {self._style(title, 1)}")
            print(f"      {self._style(description, 2)}")
        print()

    def table(self, headers: Sequence[str], rows: Iterable[Sequence[str]]) -> None:
        rows = [tuple(str(cell) for cell in row) for row in rows]
        widths = [len(header) for header in headers]
        for row in rows:
            for index, cell in enumerate(row):
                widths[index] = max(widths[index], len(cell))

        def render(row: Sequence[str]) -> str:
            return "  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row))

        print(self._style(render(headers), 36, 1))
        print(self._style("  ".join("─" * width for width in widths), 2))
        for row in rows:
            print(render(row))

    def prompt(self, label: str) -> str:
        return input(self._style(f"{label} ", 36, 1)).strip()

    @staticmethod
    def format_duration(seconds: float) -> str:
        total_seconds = max(0, round(seconds))
        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes}:{seconds:02d}"
