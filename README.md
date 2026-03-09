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
