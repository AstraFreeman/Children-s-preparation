#!/usr/bin/env python3
"""
Remove uncited BibTeX entries from bibliography.bib.

Scans all thesis .tex files (including figures/) for citation commands,
then removes any bib entry whose key is not cited.
"""

import re
import os
import sys
import glob

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BIB_FILE = os.path.join(SCRIPT_DIR, '..', 'bibliography.bib')
THESIS_DIR = os.path.join(SCRIPT_DIR, '..')


def find_cited_keys(thesis_dir):
    """Extract all citation keys from .tex files, including figures/."""
    cited = set()
    # Collect all .tex files: top-level + figures/
    tex_files = glob.glob(os.path.join(thesis_dir, '*.tex'))
    tex_files += glob.glob(os.path.join(thesis_dir, 'figures', '*.tex'))

    # Match \cite, \citep, \citet, \citealt, \citeauthor, \citeyear, etc.
    cite_re = re.compile(r'\\cite[a-z]*\*?\{([^}]+)\}')

    for path in tex_files:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        for m in cite_re.finditer(content):
            keys_str = m.group(1)
            for k in keys_str.split(','):
                k = k.strip()
                if k:
                    cited.add(k)
    return cited


def parse_bib_entries(content):
    """Parse bib file into list of (key, start, end, entry_text) tuples."""
    entries = []
    # Match each @type{key, ... } block
    pattern = re.compile(r'(@\w+\s*\{([^,]+),.*?)(?=\n@|\Z)', re.DOTALL)
    for m in pattern.finditer(content):
        entry_type_match = re.match(r'@(\w+)', m.group(1))
        if entry_type_match:
            etype = entry_type_match.group(1).lower()
            if etype in ('comment', 'string', 'preamble'):
                continue
        key = m.group(2).strip()
        entries.append({
            'key': key,
            'start': m.start(),
            'end': m.end(),
            'text': m.group(0),
        })
    return entries


def main():
    # Find all cited keys
    cited_keys = find_cited_keys(THESIS_DIR)
    print(f"Found {len(cited_keys)} unique citation keys in .tex files")

    # Read bibliography
    with open(BIB_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    entries = parse_bib_entries(content)
    print(f"Found {len(entries)} entries in bibliography.bib")

    # Classify
    bib_keys = {e['key'] for e in entries}
    cited_in_bib = cited_keys & bib_keys
    cited_not_in_bib = cited_keys - bib_keys
    uncited = bib_keys - cited_keys

    print(f"\nCited and in bib: {len(cited_in_bib)}")
    print(f"Cited but NOT in bib: {len(cited_not_in_bib)}")
    if cited_not_in_bib:
        for k in sorted(cited_not_in_bib):
            print(f"  WARNING: {k}")
    print(f"Uncited (to remove): {len(uncited)}")

    if not uncited:
        print("\nNo uncited entries to remove.")
        return

    # Create backup
    backup_path = BIB_FILE + '.bak'
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"\nBackup saved to: {backup_path}")

    # Remove uncited entries (process in reverse order to preserve positions)
    removed_keys = []
    uncited_entries = sorted(
        [e for e in entries if e['key'] in uncited],
        key=lambda e: e['start'],
        reverse=True
    )

    for entry in uncited_entries:
        text = entry['text']
        # Remove entry + trailing whitespace
        # Try removing with double newline first, then single
        if text + '\n\n' in content:
            content = content.replace(text + '\n\n', '\n', 1)
        elif text + '\n' in content:
            content = content.replace(text + '\n', '', 1)
        else:
            content = content.replace(text, '', 1)
        removed_keys.append(entry['key'])

    # Clean up excessive blank lines
    content = re.sub(r'\n{3,}', '\n\n', content)

    # Update header comment
    content = re.sub(
        r'% Total unique entries: \d+',
        f'% Total unique entries: {len(cited_in_bib)}',
        content
    )

    # Write result
    with open(BIB_FILE, 'w', encoding='utf-8') as f:
        f.write(content)

    # Verify
    with open(BIB_FILE, 'r', encoding='utf-8') as f:
        verify_content = f.read()
    verify_entries = parse_bib_entries(verify_content)

    print(f"\nRemoved {len(removed_keys)} uncited entries")
    print(f"Entries remaining: {len(verify_entries)}")

    # Check for any missing cited entries
    remaining_keys = {e['key'] for e in verify_entries}
    still_missing = cited_keys - remaining_keys
    if still_missing:
        print(f"\nWARNING: {len(still_missing)} cited keys still missing from bib:")
        for k in sorted(still_missing):
            print(f"  {k}")

    # Print removed keys (sorted)
    if '--verbose' in sys.argv:
        print("\nRemoved keys:")
        for k in sorted(removed_keys):
            print(f"  {k}")


if __name__ == '__main__':
    main()
