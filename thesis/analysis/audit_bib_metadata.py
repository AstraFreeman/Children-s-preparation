#!/usr/bin/env python3
"""
Crossref metadata audit for cited bibliography entries.

Step 2: For entries with DOI — fetch full Crossref metadata and compare.
Step 3: For entries without DOI — search Crossref by title to discover DOIs.

Outputs: metadata_audit.json with categorized issues and enrichment suggestions.
"""

import re
import os
import sys
import time
import json
import urllib.request
import urllib.parse
import urllib.error
import ssl
from difflib import SequenceMatcher

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BIB_FILE = os.path.join(SCRIPT_DIR, '..', 'bibliography.bib')
DOI_CACHE = os.path.join(SCRIPT_DIR, 'doi_cache.json')
FULL_CACHE = os.path.join(SCRIPT_DIR, 'full_metadata_cache.json')
AUDIT_OUTPUT = os.path.join(SCRIPT_DIR, 'metadata_audit.json')

CROSSREF_API = 'https://api.crossref.org/works/'
CROSSREF_MAILTO = 'mailto=serhii.korniienko@example.com'
USER_AGENT = 'BibAudit/1.0 (thesis verification; mailto:serhii.korniienko@example.com)'
REQUEST_DELAY = 0.25

# Keys that genuinely lack DOI (government docs, institutional pages, pre-DOI books, web resources)
SKIP_DOI_DISCOVERY = {
    'ZakonOsvita2017', 'UCEQA2024', 'UCEQA2025', 'KSPU', 'MON',
    'scopus', 'wos', 'dimensions',
    'Vygotsky1978', 'Csikszentmihalyi1990', 'Bonwell1991',
    'CampbellStanley1963', 'ShadishCookCampbell2002',
    'Constructivism', 'GRADE',
    'ary', 'creswell', 'guiliano', 'Milligan',
    'Korniienko2024hlg',  # web application, not a paper
    'ROMEIN',  # digital history manifesto
    'Hattie2009', 'Werbach2012', 'Yin2018', 'CohenManionMorrison2018',
    'Kirk2007', 'Borenstein2009', 'Seixas2013', 'Wineburg2001',
    'Prensky2001', 'Moretti2013', 'Fogel1974', 'Drucker2011',
    'CohenRosenzweig2006', 'Crymble2021', 'Siemens2004',
    'TamimMMRQG2021',  # book/manual
    'Lokshyna2018302', 'BychkoTereshchenko2023', 'Hlianenko2024',
    'Vovchasta2024', 'Maslova2021',  # Ukrainian institutional
    'Humeniuk2022113', 'Martynets202428', 'Zamkova2023299',
    'Striuk_2022',
}

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


def parse_bib(path):
    """Parse .bib file, extract all fields."""
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    entries = []
    pattern = re.compile(r'@(\w+)\s*\{([^,]+),\s*\n(.*?)(?=\n@|\Z)', re.DOTALL)
    for m in pattern.finditer(content):
        entry_type = m.group(1).lower()
        if entry_type in ('comment', 'string', 'preamble'):
            continue
        key = m.group(2).strip()
        body = m.group(3)

        def extract_field(name):
            pat = rf'{name}\s*=\s*(?:\{{((?:[^{{}}]|\{{[^{{}}]*\}})*)\}}|"([^"]*)"|(\d+))'
            fm = re.search(pat, body, re.IGNORECASE)
            if fm:
                return (fm.group(1) or fm.group(2) or fm.group(3) or '').strip()
            return ''

        entry = {
            'key': key,
            'type': entry_type,
            'doi': extract_field('doi'),
            'url': extract_field('url'),
            'title': re.sub(r'^\{+|\}+$', '', extract_field('title')),
            'author': extract_field('author'),
            'year': extract_field('year'),
            'journal': extract_field('journal'),
            'volume': extract_field('volume'),
            'number': extract_field('number'),
            'pages': extract_field('pages'),
            'booktitle': extract_field('booktitle'),
            'publisher': extract_field('publisher'),
        }
        entries.append(entry)

    return entries


def load_json(path):
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {}


def save_json(data, path):
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def fetch_crossref(doi):
    """Fetch full Crossref metadata for a DOI."""
    url = f'{CROSSREF_API}{urllib.parse.quote(doi, safe="")}'
    params = f'?{CROSSREF_MAILTO}'
    req = urllib.request.Request(url + params)
    req.add_header('User-Agent', USER_AGENT)

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('message', {})
    except urllib.error.HTTPError as e:
        return {'_error': e.code}
    except Exception as e:
        return {'_error': str(e)}


def search_crossref(title, rows=3):
    """Search Crossref by bibliographic query."""
    params = urllib.parse.urlencode({
        'query.bibliographic': title,
        'rows': str(rows),
        'mailto': 'serhii.korniienko@example.com',
    })
    url = f'{CROSSREF_API}?{params}'
    req = urllib.request.Request(url)
    req.add_header('User-Agent', USER_AGENT)

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return data.get('message', {}).get('items', [])
    except Exception:
        return []


def extract_cr_metadata(msg):
    """Extract structured metadata from Crossref message."""
    titles = msg.get('title', [])
    title = titles[0] if titles else ''

    # Author
    authors = msg.get('author', [])
    author_str = ' and '.join(
        f"{a.get('family', '')}, {a.get('given', '')}"
        for a in authors
    ) if authors else ''

    # Year
    year = ''
    for date_field in ('published-print', 'published-online', 'issued'):
        pub = msg.get(date_field, {})
        parts = pub.get('date-parts', [[]])
        if parts and parts[0] and parts[0][0]:
            year = str(parts[0][0])
            break

    # Journal
    containers = msg.get('container-title', [])
    journal = containers[0] if containers else ''

    return {
        'title': title,
        'author': author_str,
        'year': year,
        'journal': journal,
        'volume': msg.get('volume', ''),
        'issue': msg.get('issue', ''),
        'pages': msg.get('page', ''),
        'doi': msg.get('DOI', ''),
        'type': msg.get('type', ''),
    }


def clean_title(t):
    """Normalize title for comparison."""
    t = t.lower()
    t = re.sub(r'<[^>]+>', '', t)  # Remove HTML tags
    t = re.sub(r'[{}\[\]"\'`]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def title_similarity(t1, t2):
    return SequenceMatcher(None, clean_title(t1), clean_title(t2)).ratio()


def compare_authors(bib_author, cr_author):
    """Compare author strings, return similarity."""
    def normalize(a):
        a = a.lower()
        a = re.sub(r'[{}\.]', '', a)
        a = re.sub(r'\s+', ' ', a).strip()
        # Extract last names only for comparison
        parts = re.split(r'\s+and\s+', a)
        lastnames = []
        for p in parts:
            # "Family, Given" or "Given Family"
            if ',' in p:
                lastnames.append(p.split(',')[0].strip())
            else:
                words = p.strip().split()
                if words:
                    lastnames.append(words[-1])
        return ' '.join(sorted(lastnames))

    if not bib_author or not cr_author:
        return 0.0
    return SequenceMatcher(None, normalize(bib_author), normalize(cr_author)).ratio()


def audit_doi_entries(entries, full_cache):
    """Audit entries that have DOIs against Crossref metadata."""
    doi_entries = [e for e in entries if e['doi']]
    issues = []
    enrichments = []
    new_fetches = 0

    print(f"\n=== Auditing {len(doi_entries)} entries with DOI ===")

    for i, entry in enumerate(doi_entries):
        doi = entry['doi']
        key = entry['key']

        # Fetch or use cache
        if doi in full_cache and '_error' not in full_cache[doi]:
            msg = full_cache[doi]
        else:
            msg = fetch_crossref(doi)
            full_cache[doi] = msg
            new_fetches += 1
            time.sleep(REQUEST_DELAY)

        if (i + 1) % 50 == 0:
            print(f"  Processed {i+1}/{len(doi_entries)}...")
            save_json(full_cache, FULL_CACHE)

        if '_error' in msg:
            if msg['_error'] == 404:
                issues.append({
                    'key': key,
                    'type': 'doi_not_found',
                    'doi': doi,
                    'title': entry['title'],
                })
            continue

        cr = extract_cr_metadata(msg)

        # Title comparison
        if entry['title'] and cr['title']:
            sim = title_similarity(entry['title'], cr['title'])
            if sim < 0.7:
                issues.append({
                    'key': key,
                    'type': 'title_mismatch',
                    'doi': doi,
                    'bib_title': entry['title'],
                    'cr_title': cr['title'],
                    'similarity': round(sim, 3),
                })

        # Author comparison
        if entry['author'] and cr['author']:
            asim = compare_authors(entry['author'], cr['author'])
            if asim < 0.3:
                issues.append({
                    'key': key,
                    'type': 'author_mismatch',
                    'doi': doi,
                    'bib_author': entry['author'],
                    'cr_author': cr['author'],
                    'similarity': round(asim, 3),
                })

        # Year comparison
        if entry['year'] and cr['year'] and entry['year'] != cr['year']:
            issues.append({
                'key': key,
                'type': 'year_mismatch',
                'doi': doi,
                'bib_year': entry['year'],
                'cr_year': cr['year'],
            })

        # Missing volume/pages/issue that could be enriched
        enrich = {'key': key, 'doi': doi}
        enrichable = False

        if not entry['volume'] and cr['volume']:
            enrich['add_volume'] = cr['volume']
            enrichable = True
        if not entry['pages'] and cr['pages']:
            enrich['add_pages'] = cr['pages']
            enrichable = True
        if not entry['number'] and cr['issue']:
            enrich['add_number'] = cr['issue']
            enrichable = True

        # Check for truncated titles (bib title is a prefix of cr title)
        if entry['title'] and cr['title']:
            bib_clean = clean_title(entry['title'])
            cr_clean = clean_title(cr['title'])
            if len(bib_clean) < len(cr_clean) * 0.8 and cr_clean.startswith(bib_clean[:20]):
                enrich['fix_title'] = cr['title']
                enrichable = True

        if enrichable:
            enrichments.append(enrich)

    save_json(full_cache, FULL_CACHE)
    print(f"  New API fetches: {new_fetches}")
    return issues, enrichments


def discover_dois(entries, full_cache):
    """Try to find DOIs for entries that don't have one."""
    no_doi = [e for e in entries if not e['doi'] and e['key'] not in SKIP_DOI_DISCOVERY]
    discoveries = []

    print(f"\n=== DOI Discovery: {len(no_doi)} entries without DOI ===")
    print(f"  (Skipping {len(SKIP_DOI_DISCOVERY)} known non-DOI entries)")

    for i, entry in enumerate(no_doi):
        key = entry['key']
        title = entry['title']
        if not title:
            continue

        # Search Crossref
        results = search_crossref(title, rows=3)
        time.sleep(REQUEST_DELAY)

        for item in results:
            cr_titles = item.get('title', [])
            cr_title = cr_titles[0] if cr_titles else ''
            sim = title_similarity(title, cr_title)

            # Year match
            cr_year = ''
            for df in ('published-print', 'published-online', 'issued'):
                pub = item.get(df, {})
                parts = pub.get('date-parts', [[]])
                if parts and parts[0] and parts[0][0]:
                    cr_year = str(parts[0][0])
                    break

            year_match = (not entry['year'] or not cr_year or entry['year'] == cr_year)

            if sim > 0.85 and year_match:
                cr_doi = item.get('DOI', '')
                if cr_doi:
                    discoveries.append({
                        'key': key,
                        'discovered_doi': cr_doi,
                        'bib_title': title,
                        'cr_title': cr_title,
                        'similarity': round(sim, 3),
                        'year': entry['year'],
                    })
                    # Cache the full metadata
                    full_cache[cr_doi] = item
                    print(f"  Found DOI for {key}: {cr_doi} (sim={sim:.2f})")
                    break
        else:
            if (i + 1) % 10 == 0:
                print(f"  Processed {i+1}/{len(no_doi)}...")

    save_json(full_cache, FULL_CACHE)
    return discoveries


def find_scopus_url_removals(entries):
    """Find entries with both DOI and Scopus URL (URL is redundant)."""
    removals = []
    for entry in entries:
        if entry['doi'] and entry['url'] and 'scopus.com' in entry['url'].lower():
            removals.append({
                'key': entry['key'],
                'url': entry['url'],
            })
    return removals


def main():
    print("=== Bibliography Metadata Audit ===\n")

    # Parse bibliography
    entries = parse_bib(BIB_FILE)
    print(f"Entries in bibliography: {len(entries)}")

    doi_count = sum(1 for e in entries if e['doi'])
    no_doi_count = len(entries) - doi_count
    print(f"  With DOI: {doi_count}")
    print(f"  Without DOI: {no_doi_count}")

    # Load caches
    full_cache = load_json(FULL_CACHE)

    # Step 2: Audit DOI entries
    issues, enrichments = audit_doi_entries(entries, full_cache)

    # Step 3: DOI discovery
    discoveries = discover_dois(entries, full_cache)

    # Find Scopus URL removals
    scopus_removals = find_scopus_url_removals(entries)

    # Summary
    print(f"\n=== Audit Summary ===")

    issue_types = {}
    for iss in issues:
        t = iss['type']
        issue_types[t] = issue_types.get(t, 0) + 1
    for t, c in sorted(issue_types.items()):
        print(f"  {t}: {c}")

    print(f"  Enrichable entries: {len(enrichments)}")
    print(f"  DOIs discovered: {len(discoveries)}")
    print(f"  Scopus URLs to remove: {len(scopus_removals)}")

    # Save audit results
    audit_result = {
        'summary': {
            'total_entries': len(entries),
            'with_doi': doi_count,
            'without_doi': no_doi_count,
            'issues_found': len(issues),
            'enrichments': len(enrichments),
            'dois_discovered': len(discoveries),
            'scopus_urls': len(scopus_removals),
        },
        'issues': issues,
        'enrichments': enrichments,
        'discoveries': discoveries,
        'scopus_url_removals': scopus_removals,
    }
    save_json(audit_result, AUDIT_OUTPUT)
    print(f"\nAudit results saved to: {AUDIT_OUTPUT}")


if __name__ == '__main__':
    main()
