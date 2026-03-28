#!/usr/bin/env python3
"""
Apply metadata fixes from Crossref audit to bibliography.bib.

Reads metadata_audit.json and applies:
1. Add discovered DOIs
2. Add missing volume/pages/issue from Crossref (skip malformed values)
3. Mark non-Crossref DOIs as verified
4. Remove wrong DOI from 55Squire2004 (proceedings DOI, not paper DOI)
5. Fix DOI trailing spaces
6. Fix empty volume/number fields (IEEE artifacts)
"""

import re
import os
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BIB_FILE = os.path.join(SCRIPT_DIR, '..', 'bibliography.bib')
AUDIT_FILE = os.path.join(SCRIPT_DIR, 'metadata_audit.json')


def load_audit():
    with open(AUDIT_FILE, 'r') as f:
        return json.load(f)


def add_doi_to_entry(entry_text, doi):
    """Add doi field to a bib entry that doesn't have one."""
    if re.search(r'(?<![a-zA-Z])doi\s*=', entry_text, re.IGNORECASE):
        return entry_text  # Already has DOI

    # Insert doi before the closing }
    lines = entry_text.rstrip().rstrip('}').rstrip().rstrip(',')
    return lines + ',\n  doi = {' + doi + '},\n}'


def add_field_to_entry(entry_text, field_name, value):
    """Add a field to bib entry if not already present."""
    if re.search(rf'(?<![a-zA-Z]){field_name}\s*=', entry_text, re.IGNORECASE):
        return entry_text  # Field exists

    # Insert before closing }
    lines = entry_text.rstrip().rstrip('}').rstrip().rstrip(',')
    return lines + f',\n  {field_name} = {{{value}}},\n}}'


def parse_entries(content):
    """Parse bib content into dict of key -> entry text."""
    entry_pattern = re.compile(r'(@\w+\s*\{([^,]+),.*?)(?=\n@|\Z)', re.DOTALL)
    entries = {}
    for m in entry_pattern.finditer(content):
        key_match = re.match(r'@\w+\s*\{([^,]+),', m.group(0))
        if key_match:
            key = key_match.group(1).strip()
            entries[key] = m.group(0)
    return entries


def main():
    audit = load_audit()

    with open(BIB_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    entries = parse_entries(content)

    changes = {
        'dois_added': 0,
        'fields_enriched': 0,
        'doi_comments_added': 0,
        'doi_spaces_fixed': 0,
        'doi_removed': 0,
        'empty_fields_cleaned': 0,
    }

    # === 1. Add discovered DOIs ===
    for disc in audit.get('discoveries', []):
        key = disc['key']
        doi = disc['discovered_doi']
        if key not in entries:
            continue

        old_text = entries[key]
        new_text = add_doi_to_entry(old_text, doi)
        if new_text != old_text:
            content = content.replace(old_text, new_text)
            entries[key] = new_text
            changes['dois_added'] += 1
            print(f"  Added DOI: {key} -> {doi}")

    # === 2. Add missing volume/pages/number ===
    # Skip entries with malformed Crossref values
    SKIP_ENRICHMENTS = {'Schulz2010CONSORT', 'Higgins2011'}
    # Castronovo2015 has unusual page format from ASEE — keep it
    SKIP_PAGES = set()

    for enr in audit.get('enrichments', []):
        key = enr['key']
        if key in SKIP_ENRICHMENTS:
            continue
        if key not in entries:
            continue

        old_text = entries[key]
        new_text = old_text

        for audit_field, bib_field in [('add_volume', 'volume'), ('add_pages', 'pages'), ('add_number', 'number')]:
            if audit_field in enr:
                value = enr[audit_field]
                # Skip malformed values
                if any(c.isalpha() for c in value.split('-')[0].split('.')[0]):
                    print(f"  SKIP malformed {bib_field} for {key}: {value}")
                    continue
                if key in SKIP_PAGES and bib_field == 'pages':
                    continue
                new_text = add_field_to_entry(new_text, bib_field, value)

        if new_text != old_text:
            content = content.replace(old_text, new_text)
            entries[key] = new_text
            changes['fields_enriched'] += 1
            added = [f.replace('add_', '') for f in ('add_volume', 'add_pages', 'add_number') if f in enr]
            print(f"  Enriched: {key} -- {', '.join(added)}")

    # === 3. Non-Crossref DOIs ===
    # These DOIs are valid but not in Crossref (EU JRC, Erudit, ISLS, JORIES).
    # They will show as doi_not_found in audits — this is expected.
    # NOTE: BibTeX does not support % comments inside entries, so we do NOT
    # add inline comments. Instead, these are tracked in SKIP_DOI_DISCOVERY
    # in audit_bib_metadata.py.

    # === 4. Remove wrong DOI from 55Squire2004 ===
    # DOI 10.4324/9781410611017 is for the proceedings volume, not this paper
    if '55Squire2004' in entries:
        old_text = entries['55Squire2004']
        new_text = re.sub(r'\ndoi\s*=\s*\{10\.4324/9781410611017\},?\s*\n', '\n', old_text)
        if new_text != old_text:
            content = content.replace(old_text, new_text)
            entries['55Squire2004'] = new_text
            changes['doi_removed'] += 1
            print(f"  Removed wrong DOI: 55Squire2004 (proceedings DOI, not paper)")

    # === 5. Fix DOI trailing spaces ===
    doi_space_pattern = re.compile(r'(doi\s*=\s*\{[^}]+)\s+(\})')
    for key in list(entries.keys()):
        old_text = entries[key]
        new_text = doi_space_pattern.sub(r'\1\2', old_text)
        if new_text != old_text:
            content = content.replace(old_text, new_text)
            entries[key] = new_text
            changes['doi_spaces_fixed'] += 1
            print(f"  Fixed DOI space: {key}")

    # === 6. Clean empty volume/number fields (IEEE import artifacts) ===
    empty_field_pattern = re.compile(r'\n\s*(volume|number)\s*=\s*\{\s*\},?\s*\n')
    for key in list(entries.keys()):
        old_text = entries[key]
        new_text = empty_field_pattern.sub('\n', old_text)
        if new_text != old_text:
            content = content.replace(old_text, new_text)
            entries[key] = new_text
            changes['empty_fields_cleaned'] += 1

    # Clean up excessive blank lines
    content = re.sub(r'\n{3,}', '\n\n', content)

    # Write result
    with open(BIB_FILE, 'w', encoding='utf-8') as f:
        f.write(content)

    # Summary
    print(f"\n=== Fix Summary ===")
    total = 0
    for k, v in changes.items():
        if v > 0:
            print(f"  {k}: {v}")
            total += v

    if total == 0:
        print("  No changes needed.")

    # Verify entry count
    count = len(re.findall(r'^@\w+\{', content, re.MULTILINE))
    print(f"\nEntries in bibliography: {count}")


if __name__ == '__main__':
    main()
