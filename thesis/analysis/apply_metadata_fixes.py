#!/usr/bin/env python3
"""
Apply metadata fixes from Crossref audit to bibliography.bib.

Reads metadata_audit.json and applies:
1. Add discovered DOIs
2. Add missing volume/pages/issue from Crossref
3. Fix title for Ovcharuk2023 (wrong title, correct DOI)
4. Mark non-Crossref DOIs as verified
5. Fix trailing spaces in DOI fields
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
    # Find the closing brace; add doi before it
    # Look for the last field line before }
    if re.search(r'doi\s*=', entry_text, re.IGNORECASE):
        return entry_text  # Already has DOI

    # Insert doi before the closing }
    # Find last field = value line
    lines = entry_text.rstrip().rstrip('}').rstrip().rstrip(',')
    return lines + ',\n  doi = {' + doi + '},\n}'


def add_field_to_entry(entry_text, field_name, value):
    """Add a field to bib entry if not already present."""
    if re.search(rf'\b{field_name}\s*=', entry_text, re.IGNORECASE):
        return entry_text  # Field exists

    # Insert before closing }
    lines = entry_text.rstrip().rstrip('}').rstrip().rstrip(',')
    return lines + f',\n  {field_name} = {{{value}}},\n}}'


def fix_field_value(entry_text, field_name, old_value_pattern, new_value):
    """Replace field value in entry."""
    pattern = rf'({field_name}\s*=\s*\{{){old_value_pattern}(\}})'
    return re.sub(pattern, rf'\g<1>{new_value}\2', entry_text, flags=re.IGNORECASE | re.DOTALL)


def main():
    audit = load_audit()

    with open(BIB_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parse entries for matching
    entry_pattern = re.compile(r'(@\w+\s*\{([^,]+),.*?)(?=\n@|\Z)', re.DOTALL)
    entries = {}
    for m in entry_pattern.finditer(content):
        key_match = re.match(r'@\w+\s*\{([^,]+),', m.group(0))
        if key_match:
            key = key_match.group(1).strip()
            entries[key] = {
                'text': m.group(0),
                'start': m.start(),
                'end': m.end(),
            }

    changes = {
        'dois_added': 0,
        'fields_enriched': 0,
        'titles_fixed': 0,
        'doi_comments_added': 0,
        'doi_spaces_fixed': 0,
    }

    # === 1. Add discovered DOIs ===
    for disc in audit.get('discoveries', []):
        key = disc['key']
        doi = disc['discovered_doi']
        if key not in entries:
            print(f"  WARNING: {key} not found for DOI addition")
            continue

        old_text = entries[key]['text']
        new_text = add_doi_to_entry(old_text, doi)
        if new_text != old_text:
            content = content.replace(old_text, new_text)
            entries[key]['text'] = new_text
            changes['dois_added'] += 1
            print(f"  Added DOI: {key} → {doi}")

    # === 2. Add missing volume/pages/number ===
    # Skip entries with weird values
    SKIP_ENRICHMENTS = {'Schulz2010CONSORT'}  # "mar23 1" is malformed
    SKIP_FIELDS = {}  # (key, field) pairs to skip

    for enr in audit.get('enrichments', []):
        key = enr['key']
        if key in SKIP_ENRICHMENTS:
            continue
        if key not in entries:
            print(f"  WARNING: {key} not found for enrichment")
            continue

        old_text = entries[key]['text']
        new_text = old_text

        for audit_field, bib_field in [('add_volume', 'volume'), ('add_pages', 'pages'), ('add_number', 'number')]:
            if audit_field in enr:
                value = enr[audit_field]
                if (key, bib_field) in SKIP_FIELDS:
                    continue
                new_text = add_field_to_entry(new_text, bib_field, value)

        if new_text != old_text:
            content = content.replace(old_text, new_text)
            entries[key]['text'] = new_text
            changes['fields_enriched'] += 1
            added = [f for f in ('add_volume', 'add_pages', 'add_number') if f in enr]
            print(f"  Enriched: {key} — {', '.join(f.replace('add_', '') for f in added)}")

    # === 3. Fix Ovcharuk2023 title ===
    if 'Ovcharuk2023' in entries:
        old_text = entries['Ovcharuk2023']['text']
        new_text = old_text.replace(
            'Digital competence of Ukrainian educators in wartime: challenges and strategies',
            'Impact of school lockdown on access to online instruction during the war in Ukraine'
        )
        if new_text != old_text:
            content = content.replace(old_text, new_text)
            entries['Ovcharuk2023']['text'] = new_text
            changes['titles_fixed'] += 1
            print(f"  Fixed title: Ovcharuk2023")

    # === 4. Mark non-Crossref DOIs as verified ===
    NON_CROSSREF_DOIS = {
        'Vuorikari2016': '10.2791/11517',      # EU JRC
        'Carretero2017': '10.2760/38842',       # EU JRC (DigComp 2.1)
        'Vuorikari2022': '10.2760/115376',      # EU JRC (DigComp 2.2)
        'Redecker2017': '10.2760/159770',       # EU JRC (DigCompEdu)
        'Cosgrove2025': '10.2760/0001149',      # EU JRC (DigComp 3.0)
        '29Stiso20201165': '10.22318/icls2020.1165',  # ISLS
        '61Karsenti202027': '10.26220/rev.3278',       # Erudit
        'Ho2024139': '10.6209/JORIES.202409_69(3).0005',  # Taiwan JORIES
        'Martynets202428': '10.26220/aca.5001',        # Erudit/Academic
    }

    for key, doi in NON_CROSSREF_DOIS.items():
        if key not in entries:
            continue
        old_text = entries[key]['text']
        # Check if already marked
        if '%doi-verified' in old_text or '% doi-verified' in old_text:
            continue
        # Add comment after the doi field
        doi_escaped = re.escape(doi)
        pattern = rf'(doi\s*=\s*\{{{doi_escaped}\}})'
        replacement = r'\1  % doi-verified (non-Crossref)'
        new_text = re.sub(pattern, replacement, old_text, flags=re.IGNORECASE)
        if new_text != old_text:
            content = content.replace(old_text, new_text)
            entries[key]['text'] = new_text
            changes['doi_comments_added'] += 1

    # === 5. Fix DOI trailing spaces ===
    # 55Squire2004 has trailing space in DOI
    doi_space_pattern = re.compile(r'(doi\s*=\s*\{[^}]+)\s+(\})')
    for key, entry_data in entries.items():
        old_text = entry_data['text']
        new_text = doi_space_pattern.sub(r'\1\2', old_text)
        if new_text != old_text:
            content = content.replace(old_text, new_text)
            entries[key]['text'] = new_text
            changes['doi_spaces_fixed'] += 1
            print(f"  Fixed DOI space: {key}")

    # Write result
    with open(BIB_FILE, 'w', encoding='utf-8') as f:
        f.write(content)

    # Summary
    print(f"\n=== Fix Summary ===")
    for k, v in changes.items():
        if v > 0:
            print(f"  {k}: {v}")

    # Verify entry count
    count = len(re.findall(r'^@\w+\{', content, re.MULTILINE))
    print(f"\nEntries in bibliography: {count}")


if __name__ == '__main__':
    main()
