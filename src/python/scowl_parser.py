"""
SCOWL word list parser.

Copyright (c) 2025 John Byrd
https://github.com/johnwbyrd/bloomer

SPDX-License-Identifier: BSD-3-Clause
"""
from pathlib import Path
from typing import List


class SCOWLParser:
    """Parse SCOWL word list files."""

    SEPARATOR = "---"

    def parse(self, file_path: Path) -> List[str]:
        """Load words from SCOWL file, skipping header."""
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        separator_index = self._find_separator(lines)

        if separator_index == -1:
            print("Warning: No separator '---' found, processing entire file")
            words = [line.strip().upper() for line in lines if line.strip()]
        else:
            print(f"Found separator at line {separator_index + 1}, skipping header")
            words = [line.strip().upper()
                    for line in lines[separator_index + 1:]
                    if line.strip()]

        print(f"Loaded {len(words)} words from word list")
        return words

    def _find_separator(self, lines: List[str]) -> int:
        """Find the separator line index."""
        for i, line in enumerate(lines):
            if line.strip() == self.SEPARATOR:
                return i
        return -1
