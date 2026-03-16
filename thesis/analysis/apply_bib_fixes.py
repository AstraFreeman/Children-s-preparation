#!/usr/bin/env python3
"""
Apply verified DOI/URL fixes to bibliography.bib.
Based on reference_verification_report.txt results.
"""

import re
import os

BIB_FILE = os.path.join(os.path.dirname(__file__), '..', 'bibliography.bib')

# ─── DOI Corrections (cited entries) ─────────────────────────────────
DOI_FIXES = {
    'Calandra2005323':   ('10', '10.1016/j.iheduc.2005.09.007'),
    'Lan2023':           ('10.3389/fmed.2023.1074888', '10.3389/fmed.2023.1160289'),
    'Lai2024jama':       ('10.1001/jamanetworkopen.2024.40854', '10.1001/jamanetworkopen.2024.12687'),
    'Xia2025':           ('10.1002/jrsm.1789', '10.1017/rsm.2025.10028'),
    'Kim2025bmj':        ('10.1136/bmjebm-2024-112928', '10.1136/bmjebm-2024-113066'),
    'Purewal2025':       ('10.1136/rapm-2024-106047', '10.1136/rapm-2024-106358'),
    'Landers2019':       ('10.1177/1046878119871746', '10.1177/1046878118774385'),
    'BlackWiliam1998':   ('10.1080/7481', '10.1080/0969595980050102'),
    'McCrindle2013':     ('10.1007/978-3-642-39194-1_2', '10.1007/978-3-642-39194-1_23'),
    'MarquesCruz2025':   ('10.1002/jrsm.1751', '10.1017/rsm.2024.14'),
    'DiPumpo2025':       ('10.1093/eurpub/ckaf057', '10.1093/eurpub/ckaf072'),
    'Ovcharuk2023':      ('10.1111/ejed.12576', '10.1111/ejed.12589'),
}

# ─── Entries to remove (uncited + broken DOI) ────────────────────────
REMOVE_KEYS = {
    'Gellner2021188', 'Granados2024249', 'LeeMolebash', 'Lesley202353',
    'Reyes2024', 'Tsai2024154', 'zenodo', 'Chachra201928', 'Nguyen2023999',
}

# ─── Zielezinski20141137: move DOI→URL (DOI field contains a URL) ───
MOVE_DOI_TO_URL = {'Zielezinski20141137'}


def parse_entries_with_positions(content):
    """Parse bib entries with their exact start/end positions."""
    entries = []
    pattern = r'(@\w+\s*\{[^,]+,.*?)(?=\n@|\Z)'
    for m in re.finditer(pattern, content, re.DOTALL):
        block = m.group(1)
        # Extract key
        key_match = re.match(r'@\w+\s*\{([^,]+),', block)
        if key_match:
            key = key_match.group(1).strip()
            entries.append({
                'key': key,
                'start': m.start(),
                'end': m.end(),
                'text': block,
            })
    return entries


def fix_doi_in_entry(text, old_doi, new_doi):
    """Replace DOI value in an entry block."""
    # Escape special regex chars in old_doi
    escaped = re.escape(old_doi)
    pattern = rf'(doi\s*=\s*\{{){escaped}(\}})'
    replacement = rf'\g<1>{new_doi}\2'
    result = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    if result == text:
        # Try without braces
        pattern2 = rf'(doi\s*=\s*){escaped}(\s*[,\}}])'
        result = re.sub(pattern2, rf'\g<1>{new_doi}\2', text, flags=re.IGNORECASE)
    return result


def remove_scopus_urls(text):
    """Remove Scopus URL field from an entry that has a DOI."""
    has_doi = bool(re.search(r'doi\s*=', text, re.IGNORECASE))
    has_scopus_url = bool(re.search(r'url\s*=\s*\{https?://www\.scopus\.com', text, re.IGNORECASE))
    if has_doi and has_scopus_url:
        # Remove the entire url = {...} line (may span multiple lines)
        text = re.sub(r'\s*url\s*=\s*\{[^}]*\}\s*,?', '', text, flags=re.IGNORECASE)
    return text


def main():
    with open(BIB_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    entries = parse_entries_with_positions(content)
    print(f"Parsed {len(entries)} entries")

    # Track changes
    doi_fixed = 0
    removed = 0
    urls_cleaned = 0
    doi_moved = 0

    # Build new content by processing entries in reverse order (so positions stay valid)
    # First, collect entries to remove
    remove_positions = []
    for entry in entries:
        if entry['key'] in REMOVE_KEYS:
            remove_positions.append((entry['start'], entry['end'], entry['key']))

    # Process entry by entry
    # Build a map of key -> entry
    key_map = {}
    for entry in entries:
        key_map[entry['key']] = entry

    # Apply DOI fixes
    for key, (old_doi, new_doi) in DOI_FIXES.items():
        if key not in key_map:
            print(f"  WARNING: Key {key} not found in bib!")
            continue
        entry = key_map[key]
        old_text = entry['text']
        new_text = fix_doi_in_entry(old_text, old_doi, new_doi)
        if new_text != old_text:
            content = content.replace(old_text, new_text)
            entry['text'] = new_text  # Update for further processing
            doi_fixed += 1
            print(f"  Fixed DOI: {key}: {old_doi} → {new_doi}")
        else:
            print(f"  WARNING: Could not fix DOI for {key}")

    # Handle Zielezinski20141137: move DOI to URL
    for key in MOVE_DOI_TO_URL:
        if key not in key_map:
            continue
        entry = key_map[key]
        old_text = entry['text']
        # Remove the DOI field that contains a URL
        new_text = re.sub(
            r'\s*doi\s*=\s*\{https://www\.researchgate\.net/publication/286859873\}\s*,?',
            '', old_text, flags=re.IGNORECASE
        )
        if new_text != old_text:
            content = content.replace(old_text, new_text)
            entry['text'] = new_text
            doi_moved += 1
            print(f"  Moved DOI→removed for {key} (ResearchGate URL was in DOI field)")

    # Remove Scopus URLs from cited entries that have DOIs
    # Re-parse after DOI fixes
    for entry in entries:
        old_text = entry['text']
        # Only process if still in content
        if old_text not in content:
            continue
        new_text = remove_scopus_urls(old_text)
        if new_text != old_text:
            content = content.replace(old_text, new_text)
            entry['text'] = new_text
            urls_cleaned += 1

    # Remove uncited broken entries
    for key in REMOVE_KEYS:
        if key not in key_map:
            print(f"  WARNING: Key {key} not found for removal!")
            continue
        entry = key_map[key]
        old_text = entry['text']
        if old_text in content:
            # Remove the entry and any trailing whitespace/newlines
            content = content.replace(old_text + '\n\n', '\n')
            if old_text in content:
                content = content.replace(old_text + '\n', '\n')
            if old_text in content:
                content = content.replace(old_text, '')
            removed += 1
            print(f"  Removed: {key}")

    # Clean up multiple blank lines
    content = re.sub(r'\n{3,}', '\n\n', content)

    with open(BIB_FILE, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\n=== Summary ===")
    print(f"DOIs fixed: {doi_fixed}")
    print(f"Entries removed: {removed}")
    print(f"Scopus URLs cleaned: {urls_cleaned}")
    print(f"DOI→URL moved: {doi_moved}")

    # Verify entry count
    with open(BIB_FILE, 'r', encoding='utf-8') as f:
        new_content = f.read()
    new_entries = parse_entries_with_positions(new_content)
    print(f"Entries before: {len(entries)}, after: {len(new_entries)}")


if __name__ == '__main__':
    main()
