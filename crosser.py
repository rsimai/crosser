#!/usr/bin/env python3
"""Generate compact American-style crossword-like grids from a word list.

Rules enforced by the generator:
- Cells are either letters or blocks (#).
- Every across/down run that closes with length >= 2 must be a valid dictionary word.
- Length-1 runs are not allowed.
- No word may appear more than once in the grid (no duplicate words).
- The search minimizes blocks by trying solutions with 0..N blocks.
- Branching is biased toward letters that can grow into longer words.
"""

from __future__ import annotations

import argparse
import multiprocessing
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
        timeout: Optional[float] = None,
        shared_counter: Optional[multiprocessing.Value] = None,
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
        self.timeout = timeout
        self.start_time = 0.0
        self.total_fields = width * height
        self.nodes_visited = 0
        self.shared_counter = shared_counter
        self._last_status_time = 0.0
        self._last_status_line_len = 0
        self._last_counter_update = 0.0

        self.grid: List[List[str]] = [[" " for _ in range(width)] for _ in range(height)]
        self.solution: Optional[List[List[str]]] = None

    def _status_tick(self, letters: int, blocks: int, block_limit: int) -> None:
        if not self.status_enabled and self.shared_counter is None:
            return
        now = time.monotonic()
        
        # Update shared counter for parallel workers (every 0.1s)
        if self.shared_counter is not None and now - self._last_counter_update >= 0.1:
            with self.shared_counter.get_lock():
                self.shared_counter.value = self.nodes_visited
            self._last_counter_update = now
        
        # Display status line for single-threaded mode
        if not self.status_enabled:
            return
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

    def _is_valid_close(self, run: str, used_words: Optional[Set[str]] = None) -> bool:
        if not run:
            return True
        if len(run) == 1:
            return False
        if run not in self.words:
            return False
        # Check if word has already been used (no duplicates allowed)
        if used_words is not None and run in used_words:
            return False
        return True

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

        # Sort by score (descending), with random tie-breaking
        ranked.sort(key=lambda item: (item[1], self.rng.random()), reverse=True)
        return ranked

    def _search(
        self,
        idx: int,
        across_prefix: str,
        down_prefixes: List[str],
        used_letters: int,
        used_blocks: int,
        block_limit: int,
        used_words: Optional[Set[str]] = None,
    ) -> bool:
        self.nodes_visited += 1
        self._status_tick(used_letters, used_blocks, block_limit)

        # Initialize used_words set on first call
        if used_words is None:
            used_words = set()

        # Check timeout
        if self.timeout is not None:
            if time.monotonic() - self.start_time > self.timeout:
                return False

        if used_blocks > block_limit:
            return False

        total = self.width * self.height
        if idx == total:
            if not self._is_valid_close(across_prefix, used_words):
                return False
            for run in down_prefixes:
                if not self._is_valid_close(run, used_words):
                    return False
            if used_blocks < self.min_blocks:
                return False
            self.solution = [row[:] for row in self.grid]
            return True

        r, c = divmod(idx, self.width)

        # Track if we add a row boundary word (for backtracking)
        row_word_added = None
        
        # End-of-row boundary: across run must close here.
        if c == 0 and idx > 0:
            if not self._is_valid_close(across_prefix, used_words):
                return False
            # Add the completed across word to used_words if it's a valid word
            if across_prefix and len(across_prefix) >= 2:
                row_word_added = across_prefix
                used_words.add(across_prefix)
            across_prefix = ""

        down_prefix = down_prefixes[c]
        forced = self.grid[r][c]

        if forced == "#":
            # Track words that will close due to this block
            across_to_add = None
            down_to_add = None
            
            if not self._is_valid_close(across_prefix, used_words):
                # Backtrack row word before returning
                if row_word_added:
                    used_words.discard(row_word_added)
                return False
            if not self._is_valid_close(down_prefix, used_words):
                # Backtrack row word before returning
                if row_word_added:
                    used_words.discard(row_word_added)
                return False
            
            # Add completed words to used set
            if across_prefix and len(across_prefix) >= 2:
                across_to_add = across_prefix
                used_words.add(across_prefix)
            if down_prefix and len(down_prefix) >= 2:
                down_to_add = down_prefix
                used_words.add(down_prefix)
            
            down_prefixes[c] = ""
            ok = self._search(
                idx + 1,
                "",
                down_prefixes,
                used_letters,
                used_blocks,
                block_limit,
                used_words,
            )
            down_prefixes[c] = down_prefix
            
            # Backtrack: remove the words we added
            if across_to_add:
                used_words.discard(across_to_add)
            if down_to_add:
                used_words.discard(down_to_add)
            # Backtrack row word
            if row_word_added:
                used_words.discard(row_word_added)
            
            return ok

        if forced != " ":
            letter_candidates = self._possible_letters(across_prefix, down_prefix)
            if all(ch != forced for ch, _ in letter_candidates):
                # Backtrack row word before returning
                if row_word_added:
                    used_words.discard(row_word_added)
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
                used_words,
            )
            down_prefixes[c] = down_prefix
            # Backtrack row word
            if row_word_added:
                used_words.discard(row_word_added)
            return ok

        letter_candidates = self._possible_letters(across_prefix, down_prefix)

        # Early failure detection: if no letters are possible and we can't place a block,
        # fail immediately
        can_place_block = self._is_valid_close(across_prefix, used_words) and self._is_valid_close(down_prefix, used_words)
        if not letter_candidates and not can_place_block:
            # Backtrack row word before returning
            if row_word_added:
                used_words.discard(row_word_added)
            return False

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
                used_words,
            ):
                # Success - don't backtrack row word, it's part of the solution
                return True
            down_prefixes[c] = down_prefix

        # Try placing a block if both runs can legally close now.
        if can_place_block:
            sr, sc = self._symmetric_cell(r, c)
            added_blocks = 1
            added_symmetry_block = False
            across_to_add = None
            down_to_add = None
            
            if self.symmetry == "rotational":
                sym_value = self.grid[sr][sc]
                sym_idx = sr * self.width + sc
                if sym_value not in (" ", "#"):
                    self.grid[r][c] = " "
                    # Backtrack row word before returning
                    if row_word_added:
                        used_words.discard(row_word_added)
                    return False
                if sym_idx < idx and sym_value != "#":
                    self.grid[r][c] = " "
                    # Backtrack row word before returning
                    if row_word_added:
                        used_words.discard(row_word_added)
                    return False
                if (sr, sc) != (r, c) and sym_value == " ":
                    self.grid[sr][sc] = "#"
                    added_blocks += 1
                    added_symmetry_block = True

            # Add completed words to used set
            if across_prefix and len(across_prefix) >= 2:
                across_to_add = across_prefix
                used_words.add(across_prefix)
            if down_prefix and len(down_prefix) >= 2:
                down_to_add = down_prefix
                used_words.add(down_prefix)

            self.grid[r][c] = "#"
            down_prefixes[c] = ""
            if self._search(
                idx + 1,
                "",
                down_prefixes,
                used_letters,
                used_blocks + added_blocks,
                block_limit,
                used_words,
            ):
                return True
            down_prefixes[c] = down_prefix
            if added_symmetry_block:
                self.grid[sr][sc] = " "
            
            # Backtrack: remove the words we added
            if across_to_add:
                used_words.discard(across_to_add)
            if down_to_add:
                used_words.discard(down_to_add)

        self.grid[r][c] = " "
        # Backtrack row word before final return
        if row_word_added:
            used_words.discard(row_word_added)
        return False

    def generate(self, max_blocks: Optional[int] = None, start_blocks: Optional[int] = None) -> Optional[List[List[str]]]:
        if max_blocks is None:
            max_blocks = self.width * self.height
        if self.min_blocks > max_blocks:
            return None
        
        # Allow starting from a higher block count to skip unlikely solutions
        if start_blocks is None:
            start_blocks = self.min_blocks
        else:
            start_blocks = max(start_blocks, self.min_blocks)
        
        if start_blocks > max_blocks:
            return None

        down_prefixes = ["" for _ in range(self.width)]
        self.start_time = time.monotonic()

        for limit in range(start_blocks, max_blocks + 1):
            self.grid = [[" " for _ in range(self.width)] for _ in range(self.height)]
            self.solution = None
            if self._search(0, "", down_prefixes[:], 0, 0, limit):
                self._status_done()
                return self.solution
            
            # Check timeout between block limit iterations
            if self.timeout is not None:
                if time.monotonic() - self.start_time > self.timeout:
                    break

        self._status_done()
        return None


def _worker_generate(args: Tuple) -> Optional[List[List[str]]]:
    """Worker function for parallel generation. Tries a specific block limit or seed."""
    (width, height, words, seed, symmetry, min_blocks, timeout, 
     max_blocks, start_blocks, worker_id, total_workers) = args
    
    # Each worker tries a different subset of block limits
    if start_blocks is None:
        start_blocks = min_blocks
    if max_blocks is None:
        max_blocks = width * height
    
    # Distribute block limits among workers
    block_range = max_blocks - start_blocks + 1
    blocks_per_worker = max(1, block_range // total_workers)
    worker_start = start_blocks + (worker_id * blocks_per_worker)
    worker_end = min(max_blocks, worker_start + blocks_per_worker - 1) if worker_id < total_workers - 1 else max_blocks
    
    if worker_start > max_blocks:
        return None
    
    # Create a generator with a modified seed for this worker
    # Use global shared counter if available
    worker_seed = None if seed is None else seed + worker_id
    gen = CrosswordGenerator(
        width=width,
        height=height,
        words=words,
        seed=worker_seed,
        symmetry=symmetry,
        status=False,  # Disable status in workers to avoid output conflicts
        min_blocks=min_blocks,
        timeout=timeout,
        shared_counter=_SHARED_COUNTER,
    )
    
    # Try the assigned block range
    return gen.generate(max_blocks=worker_end, start_blocks=worker_start)


# Global variable to hold shared counter for multiprocessing
_SHARED_COUNTER: Optional[multiprocessing.Value] = None


def _init_worker(counter):
    """Initialize worker process with shared counter."""
    global _SHARED_COUNTER
    _SHARED_COUNTER = counter


def generate_parallel(
    width: int,
    height: int,
    words: Set[str],
    workers: int,
    seed: Optional[int] = None,
    symmetry: str = "none",
    min_blocks: int = 1,
    timeout: Optional[float] = None,
    max_blocks: Optional[int] = None,
    start_blocks: Optional[int] = None,
    status: bool = False,
) -> Optional[List[List[str]]]:
    """Generate a grid using multiple parallel workers."""
    if workers <= 1:
        # Fall back to single-threaded
        gen = CrosswordGenerator(
            width=width,
            height=height,
            words=words,
            seed=seed,
            symmetry=symmetry,
            status=status,
            min_blocks=min_blocks,
            timeout=timeout,
        )
        return gen.generate(max_blocks=max_blocks, start_blocks=start_blocks)
    
    if status:
        print(f"Starting parallel search with {workers} workers...", file=sys.stderr)
    
    # Create a shared counter to track total nodes visited across all workers
    shared_counter = multiprocessing.Value('i', 0)
    
    # Prepare arguments for each worker
    worker_args = []
    for worker_id in range(workers):
        worker_args.append((
            width, height, words, seed, symmetry, min_blocks, timeout,
            max_blocks, start_blocks, worker_id, workers
        ))
    
    # Use multiprocessing to run workers in parallel
    start_time = time.monotonic()
    last_status_time = 0.0
    last_status_line_len = 0
    
    with multiprocessing.Pool(processes=workers, initializer=_init_worker, initargs=(shared_counter,)) as pool:
        # Use imap_unordered to get results as they complete
        async_result = pool.imap_unordered(_worker_generate, worker_args)
        
        # Monitor progress while waiting for results
        while True:
            try:
                # Check for results with a short timeout
                result = async_result.next(timeout=0.5)
                if result is not None:
                    # Found a solution, terminate other workers
                    pool.terminate()
                    pool.join()
                    if status:
                        # Clear status line
                        padding = " " * last_status_line_len
                        sys.stderr.write(f"\r{padding}\r")
                        print("Solution found!", file=sys.stderr)
                    return result
            except multiprocessing.TimeoutError:
                # No result yet, update status if enabled
                pass
            except StopIteration:
                # All workers finished without finding a solution
                break
            
            # Display progress status
            if status:
                now = time.monotonic()
                if now - last_status_time >= 2.0:  # Update every 2 seconds
                    elapsed = now - start_time
                    with shared_counter.get_lock():
                        nodes = shared_counter.value
                    line = f"\rWorkers: {workers} | Nodes visited: {nodes:,} | Elapsed: {elapsed:.1f}s"
                    padding = " " * max(0, last_status_line_len - len(line))
                    sys.stderr.write(line + padding)
                    sys.stderr.flush()
                    last_status_line_len = len(line)
                    last_status_time = now
    
    if status and last_status_line_len > 0:
        # Clear status line
        padding = " " * last_status_line_len
        sys.stderr.write(f"\r{padding}\r")
        sys.stderr.flush()
    
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
        "--start-blocks",
        type=int,
        default=None,
        help="Start searching from this many blocks (default: min-blocks). "
             "Increase this to skip trying grids with very few blocks, which often fail.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Maximum time in seconds to search before giving up.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of parallel workers (CPUs) to use. Values > 1 enable parallel search. "
             "Each worker tries different block limits or random variations.",
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
    if args.start_blocks is not None and args.start_blocks < 0:
        print("--start-blocks must be >= 0.", file=sys.stderr)
        return 2
    if args.timeout is not None and args.timeout <= 0:
        print("--timeout must be > 0.", file=sys.stderr)
        return 2
    if args.workers < 1:
        print("--workers must be >= 1.", file=sys.stderr)
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

    # Use parallel generation if workers > 1
    if args.workers > 1:
        grid = generate_parallel(
            width=args.width,
            height=args.height,
            words=words,
            workers=args.workers,
            seed=args.seed,
            symmetry=args.symmetry,
            min_blocks=args.min_blocks,
            timeout=args.timeout,
            max_blocks=args.max_blocks,
            start_blocks=args.start_blocks,
            status=args.status,
        )
    else:
        gen = CrosswordGenerator(
            width=args.width,
            height=args.height,
            words=words,
            seed=args.seed,
            symmetry=args.symmetry,
            status=args.status,
            min_blocks=args.min_blocks,
            timeout=args.timeout,
        )
        grid = gen.generate(max_blocks=args.max_blocks, start_blocks=args.start_blocks)

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
