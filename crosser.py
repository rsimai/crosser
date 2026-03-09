#!/usr/bin/env python3
"""Generate compact American-style crossword-like grids from a word list.

Rules enforced by the generator:
- Cells are either letters or blocks (#).
- Every across/down run that closes with length >= 2 must be a valid dictionary word.
- Length-1 runs are not allowed.
- The search minimizes blocks by trying solutions with 0..N blocks.
- Branching is biased toward letters that can grow into longer words.
"""

from __future__ import annotations

import argparse
import random
import string
import sys
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

ALPHABET = string.ascii_uppercase


@dataclass
class TrieNode:
    children: Dict[str, "TrieNode"]
    is_word: bool
    max_word_len_from_here: int

    def __init__(self) -> None:
        self.children = {}
        self.is_word = False
        self.max_word_len_from_here = 0


class Trie:
    def __init__(self) -> None:
        self.root = TrieNode()

    def insert(self, word: str) -> None:
        node = self.root
        remaining = len(word)
        if remaining > node.max_word_len_from_here:
            node.max_word_len_from_here = remaining

        for idx, ch in enumerate(word):
            child = node.children.get(ch)
            if child is None:
                child = TrieNode()
                node.children[ch] = child
            node = child
            remaining = len(word) - (idx + 1)
            if remaining > node.max_word_len_from_here:
                node.max_word_len_from_here = remaining
        node.is_word = True

    def walk(self, prefix: str) -> Optional[TrieNode]:
        node = self.root
        for ch in prefix:
            node = node.children.get(ch)
            if node is None:
                return None
        return node


def is_clean_word(raw: str) -> bool:
    return bool(raw) and all("A" <= ch <= "Z" for ch in raw)


def load_words(path: str, min_len: int, max_len: int) -> Set[str]:
    words: Set[str] = set()
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            w = line.strip().upper()
            if not (min_len <= len(w) <= max_len):
                continue
            if not is_clean_word(w):
                continue
            words.add(w)
    return words


class CrosswordGenerator:
    def __init__(
        self,
        width: int,
        height: int,
        words: Iterable[str],
        seed: Optional[int] = None,
        symmetry: str = "none",
        status: bool = False,
        min_blocks: int = 1,
    ) -> None:
        self.width = width
        self.height = height
        self.words = set(words)
        self.trie = Trie()
        for w in self.words:
            self.trie.insert(w)

        self.rng = random.Random(seed)
        self.symmetry = symmetry
        self.status_enabled = status
        self.min_blocks = min_blocks
        self.total_fields = width * height
        self.nodes_visited = 0
        self._last_status_time = 0.0
        self._last_status_line_len = 0

        self.grid: List[List[str]] = [[" " for _ in range(width)] for _ in range(height)]
        self.solution: Optional[List[List[str]]] = None

    def _status_tick(self, letters: int, blocks: int, block_limit: int) -> None:
        if not self.status_enabled:
            return
        now = time.monotonic()
        if now - self._last_status_time < 0.05:
            return
        self._last_status_time = now
        line = (
            f"\rFields: {self.total_fields} "
            f"Letters: {letters} "
            f"Blocks: {blocks} "
            f"Visited: {self.nodes_visited} "
            f"Limit: {block_limit}"
        )
        padding = " " * max(0, self._last_status_line_len - len(line))
        sys.stdout.write(line + padding)
        sys.stdout.flush()
        self._last_status_line_len = len(line)

    def _status_done(self) -> None:
        if self.status_enabled:
            sys.stdout.write("\n")
            sys.stdout.flush()

    def _symmetric_cell(self, r: int, c: int) -> Tuple[int, int]:
        return (self.height - 1 - r, self.width - 1 - c)

    def _is_valid_close(self, run: str) -> bool:
        if not run:
            return True
        if len(run) == 1:
            return False
        return run in self.words

    def _possible_letters(self, across_prefix: str, down_prefix: str) -> List[Tuple[str, int]]:
        a_node = self.trie.walk(across_prefix)
        if a_node is None:
            return []
        d_node = self.trie.walk(down_prefix)
        if d_node is None:
            return []

        common = set(a_node.children.keys()) & set(d_node.children.keys())
        if not common:
            return []

        ranked: List[Tuple[str, int]] = []
        for ch in common:
            # Favor letters that can still lead to long words in both directions.
            score = min(
                a_node.children[ch].max_word_len_from_here,
                d_node.children[ch].max_word_len_from_here,
            )
            ranked.append((ch, score))

        self.rng.shuffle(ranked)
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked

    def _search(
        self,
        idx: int,
        across_prefix: str,
        down_prefixes: List[str],
        used_letters: int,
        used_blocks: int,
        block_limit: int,
    ) -> bool:
        self.nodes_visited += 1
        self._status_tick(used_letters, used_blocks, block_limit)

        if used_blocks > block_limit:
            return False

        total = self.width * self.height
        if idx == total:
            if not self._is_valid_close(across_prefix):
                return False
            for run in down_prefixes:
                if not self._is_valid_close(run):
                    return False
            if used_blocks < self.min_blocks:
                return False
            self.solution = [row[:] for row in self.grid]
            return True

        r, c = divmod(idx, self.width)

        # End-of-row boundary: across run must close here.
        if c == 0 and idx > 0:
            if not self._is_valid_close(across_prefix):
                return False
            across_prefix = ""

        down_prefix = down_prefixes[c]
        forced = self.grid[r][c]

        if forced == "#":
            if not (self._is_valid_close(across_prefix) and self._is_valid_close(down_prefix)):
                return False
            down_prefixes[c] = ""
            ok = self._search(
                idx + 1,
                "",
                down_prefixes,
                used_letters,
                used_blocks,
                block_limit,
            )
            down_prefixes[c] = down_prefix
            return ok

        if forced != " ":
            letter_candidates = self._possible_letters(across_prefix, down_prefix)
            if all(ch != forced for ch, _ in letter_candidates):
                return False
            down_prefixes[c] = down_prefix + forced
            next_across = across_prefix + forced
            ok = self._search(
                idx + 1,
                next_across,
                down_prefixes,
                used_letters,
                used_blocks,
                block_limit,
            )
            down_prefixes[c] = down_prefix
            return ok

        letter_candidates = self._possible_letters(across_prefix, down_prefix)

        # Try letters first to minimize blocks.
        for ch, _score in letter_candidates:
            sr, sc = self._symmetric_cell(r, c)
            if self.symmetry == "rotational" and self.grid[sr][sc] == "#":
                continue
            self.grid[r][c] = ch
            down_prefixes[c] = down_prefix + ch
            next_across = across_prefix + ch
            if self._search(
                idx + 1,
                next_across,
                down_prefixes,
                used_letters + 1,
                used_blocks,
                block_limit,
            ):
                return True
            down_prefixes[c] = down_prefix

        # Try placing a block if both runs can legally close now.
        if self._is_valid_close(across_prefix) and self._is_valid_close(down_prefix):
            sr, sc = self._symmetric_cell(r, c)
            added_blocks = 1
            added_symmetry_block = False
            if self.symmetry == "rotational":
                sym_value = self.grid[sr][sc]
                sym_idx = sr * self.width + sc
                if sym_value not in (" ", "#"):
                    self.grid[r][c] = " "
                    return False
                if sym_idx < idx and sym_value != "#":
                    self.grid[r][c] = " "
                    return False
                if (sr, sc) != (r, c) and sym_value == " ":
                    self.grid[sr][sc] = "#"
                    added_blocks += 1
                    added_symmetry_block = True

            self.grid[r][c] = "#"
            down_prefixes[c] = ""
            if self._search(
                idx + 1,
                "",
                down_prefixes,
                used_letters,
                used_blocks + added_blocks,
                block_limit,
            ):
                return True
            down_prefixes[c] = down_prefix
            if added_symmetry_block:
                self.grid[sr][sc] = " "

        self.grid[r][c] = " "
        return False

    def generate(self, max_blocks: Optional[int] = None) -> Optional[List[List[str]]]:
        if max_blocks is None:
            max_blocks = self.width * self.height
        if self.min_blocks > max_blocks:
            return None

        down_prefixes = ["" for _ in range(self.width)]

        for limit in range(self.min_blocks, max_blocks + 1):
            self.grid = [[" " for _ in range(self.width)] for _ in range(self.height)]
            self.solution = None
            if self._search(0, "", down_prefixes[:], 0, 0, limit):
                self._status_done()
                return self.solution

        self._status_done()
        return None


def extract_numbered_entries(grid: List[List[str]]) -> Tuple[List[str], List[str]]:
    h = len(grid)
    w = len(grid[0]) if h else 0
    number = 1
    across: List[str] = []
    down: List[str] = []

    def is_letter(rr: int, cc: int) -> bool:
        return 0 <= rr < h and 0 <= cc < w and grid[rr][cc] != "#"

    for r in range(h):
        for c in range(w):
            if grid[r][c] == "#":
                continue

            starts_across = (c == 0 or grid[r][c - 1] == "#") and is_letter(r, c + 1)
            starts_down = (r == 0 or grid[r - 1][c] == "#") and is_letter(r + 1, c)
            if not (starts_across or starts_down):
                continue

            if starts_across:
                cc = c
                chars: List[str] = []
                while cc < w and grid[r][cc] != "#":
                    chars.append(grid[r][cc])
                    cc += 1
                across.append(f"{number}. ({r + 1},{c + 1}) {''.join(chars)}")

            if starts_down:
                rr = r
                chars = []
                while rr < h and grid[rr][c] != "#":
                    chars.append(grid[rr][c])
                    rr += 1
                down.append(f"{number}. ({r + 1},{c + 1}) {''.join(chars)}")

            number += 1

    return across, down


def render_grid(grid: List[List[str]]) -> str:
    width = len(grid[0]) if grid else 0
    border = "+" + "-" * (2 * width - 1) + "+"
    lines = [border]
    for row in grid:
        lines.append("|" + " ".join(row) + "|")
    lines.append(border)
    return "\n".join(lines)


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a compact crossword-like grid.")
    parser.add_argument("--width", type=int, default=8, help="Grid width.")
    parser.add_argument("--height", type=int, default=8, help="Grid height.")
    parser.add_argument(
        "--dict",
        dest="dict_path",
        default="/usr/share/dict/american",
        help="Path to dictionary file (one word per line).",
    )
    parser.add_argument(
        "--max-blocks",
        type=int,
        default=None,
        help="Optional upper bound for block count.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for tie-breaking in search order.",
    )
    parser.add_argument(
        "--symmetry",
        choices=["none", "rotational"],
        default="none",
        help="Block-layout symmetry mode.",
    )
    parser.add_argument(
        "--min-blocks",
        type=int,
        default=1,
        help="Require at least this many blocks in the final grid.",
    )
    parser.add_argument(
        "--numbered",
        action="store_true",
        help="Print numbered Across/Down entries after the grid.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show one-line live progress while searching.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Write final output to this file instead of stdout.",
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)

    if args.width < 2 or args.height < 2:
        print("Width and height must both be >= 2.", file=sys.stderr)
        return 2
    if args.min_blocks < 0:
        print("--min-blocks must be >= 0.", file=sys.stderr)
        return 2
    if args.max_blocks is not None and args.max_blocks < args.min_blocks:
        print("--max-blocks must be >= --min-blocks.", file=sys.stderr)
        return 2
    if args.symmetry == "rotational" and (args.width * args.height) % 2 == 0:
        if args.min_blocks % 2 == 1:
            print(
                "With rotational symmetry on an even-sized grid, --min-blocks must be even.",
                file=sys.stderr,
            )
            return 2

    max_word_len = max(args.width, args.height)
    words = load_words(args.dict_path, min_len=2, max_len=max_word_len)
    if not words:
        print(
            "No usable words found. Check dictionary path and word filtering.",
            file=sys.stderr,
        )
        return 2

    gen = CrosswordGenerator(
        width=args.width,
        height=args.height,
        words=words,
        seed=args.seed,
        symmetry=args.symmetry,
        status=args.status,
        min_blocks=args.min_blocks,
    )
    grid = gen.generate(max_blocks=args.max_blocks)

    if grid is None:
        print("No valid grid found with the given constraints.", file=sys.stderr)
        return 1

    output_lines: List[str] = [render_grid(grid)]
    blocks = sum(ch == "#" for row in grid for ch in row)
    output_lines.append(f"Blocks: {blocks}")
    if args.numbered:
        across, down = extract_numbered_entries(grid)
        output_lines.append("Across:")
        for entry in across:
            output_lines.append(entry)
        output_lines.append("Down:")
        for entry in down:
            output_lines.append(entry)

    output_text = "\n".join(output_lines)
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as handle:
                handle.write(output_text + "\n")
        except OSError as exc:
            print(f"Failed to write output file '{args.output}': {exc}", file=sys.stderr)
            return 2
    else:
        print(output_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
