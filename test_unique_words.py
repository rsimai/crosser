#!/usr/bin/env python3
"""Test script to verify that generated crosswords have no duplicate words."""

import sys
import re


def extract_words_from_output(output):
    """Extract all words from numbered crossword output."""
    words = []
    in_across = False
    in_down = False
    
    for line in output.split('\n'):
        if line.strip() == 'Across:':
            in_across = True
            in_down = False
            continue
        elif line.strip() == 'Down:':
            in_across = False
            in_down = True
            continue
        
        if in_across or in_down:
            # Match pattern like "1. (1,1) WORD"
            match = re.search(r'\)\s+([A-Z]+)$', line)
            if match:
                words.append(match.group(1))
    
    return words


def check_for_duplicates(words):
    """Check if there are any duplicate words."""
    seen = set()
    duplicates = set()
    
    for word in words:
        if word in seen:
            duplicates.add(word)
        seen.add(word)
    
    return duplicates


if __name__ == "__main__":
    # Read from stdin or file
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r') as f:
            output = f.read()
    else:
        output = sys.stdin.read()
    
    words = extract_words_from_output(output)
    
    if not words:
        print("No words found in output!")
        sys.exit(1)
    
    print(f"Found {len(words)} total words:")
    print(f"  {', '.join(words)}")
    print()
    
    duplicates = check_for_duplicates(words)
    
    if duplicates:
        print(f"❌ DUPLICATES FOUND: {', '.join(sorted(duplicates))}")
        sys.exit(1)
    else:
        print(f"✓ All {len(words)} words are unique - no duplicates!")
        sys.exit(0)
