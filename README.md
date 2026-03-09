# Crosser

Minimal Python 3 crossword-grid generator using only the standard library.

## What It Does

- Builds a 2D grid with configurable `width` and `height`
- Uses words from a configurable text file (one word per line)
- Rejects entries with apostrophes or non-letters
- Enforces American-style blocks (`#`) between words
- Ensures every across/down run with length >= 2 is a valid dictionary word
- Searches for a fill with as few blocks as possible
- Prefers branches that can grow into longer words first
- Supports rotational block symmetry (`--symmetry rotational`)
- Requires at least one block by default (`--min-blocks 1`)
- Can print numbered Across/Down entry export (`--numbered`)
- Can show live one-line search status (`--status`)
- Can write final result to a file (`--output`)
- Prints an ASCII grid suitable for fixed-width console fonts

## Usage

```bash
python3 crosser.py --width 8 --height 8 --dict /usr/share/dict/american
```

Optional flags:

- `--max-blocks N` to cap block count during search
- `--start-blocks N` to start searching from N blocks (default: min-blocks). Increase this to skip trying grids with very few blocks, which often fail for larger grids
- `--timeout SECONDS` to limit search time (e.g., `--timeout 60` for 1 minute)
- `--workers N` to use N parallel CPU workers (default: 1). Values > 1 enable parallel search where each worker tries different block limits
- `--seed N` to make tie-breaking deterministic
- `--symmetry {none,rotational}` for block pattern symmetry
- `--min-blocks N` to require a minimum number of blocks
- `--numbered` to print numbered Across/Down entries
- `--status` to show a refreshing progress line
- `--output FILE` to write result to a file instead of stdout

Example:

```bash
python3 crosser.py --width 10 --height 6 --dict /usr/share/dict/american --seed 42
```

Numbered export with symmetry and progress:

```bash
python3 crosser.py --width 8 --height 8 --dict /usr/share/dict/american --symmetry rotational --numbered --status
```

Write result to a file:

```bash
python3 crosser.py --width 8 --height 8 --dict /usr/share/dict/american --output puzzle.txt
```

## Notes

- Large grids can be slow because this is a constrained backtracking search.
- The script filters dictionary words to lengths between `2` and `max(width, height)`.
- With `--symmetry rotational` on even-sized grids, use an even `--min-blocks` value.

## Performance Tuning

For faster results, especially with larger grids:

1. **Use `--workers`**: Utilize multiple CPU cores to search in parallel. Each worker explores different block limits simultaneously. Example: `--workers 4` to use 4 CPU cores. This can significantly speed up finding solutions.

2. **Use `--start-blocks`**: Skip trying grids with very few blocks, which rarely succeed. For an 8x8 grid, try `--start-blocks 8` to start from 8 blocks instead of 1.

3. **Use `--timeout`**: Set a time limit to prevent infinite searching. Example: `--timeout 120` for 2 minutes.

4. **Use `--status`**: Monitor progress and nodes visited to gauge if the search is making progress.

5. **Adjust grid size**: Smaller grids (5x5, 6x6) fill much faster than larger ones (10x10+).

Example for best performance on an 8x8 grid:

```bash
python3 crosser.py --width 8 --height 8 --dict /usr/share/dict/american --workers 4 --start-blocks 8 --timeout 60 --status
```

Example for a challenging 10x10 grid:

```bash
python3 crosser.py --width 10 --height 10 --dict /usr/share/dict/american --workers 8 --start-blocks 15 --timeout 300 --status
```

**Why these help:**

- **Parallel workers** explore multiple configurations simultaneously, dramatically reducing wall-clock time on multi-core CPUs. Each worker tries different block limits, and the first to succeed returns the result.
- The algorithm tries to minimize blocks, starting from `min-blocks` and incrementing. For an 8x8 grid (64 cells), grids with only 1-7 blocks are usually impossible to fill with valid words, so skipping them saves time.
- Timeouts prevent the search from running indefinitely on difficult configurations.
- Early failure detection now prunes impossible branches faster (optimized in recent updates).
