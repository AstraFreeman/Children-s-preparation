#!/usr/bin/env python3
"""
Systematic bibliography reference verification.

Checks all DOIs via CrossRef API, cross-verifies metadata,
finds correct DOIs for broken cited entries, and checks URLs.
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
from collections import defaultdict

# Paths
BIB_FILE = os.path.join(os.path.dirname(__file__), '..', 'bibliography.bib')
THESIS_DIR = os.path.join(os.path.dirname(__file__), '..')
REPORT_FILE = os.path.join(os.path.dirname(__file__), 'reference_verification_report.txt')
CACHE_FILE = os.path.join(os.path.dirname(__file__), 'doi_cache.json')

# CrossRef API settings
CROSSREF_API = 'https://api.crossref.org/works/'
CROSSREF_MAILTO = 'mailto=serhii.korniienko@example.com'
REQUEST_DELAY = 0.25  # 4 req/s, polite

# SSL context for URL checks
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


def parse_bib(path):
    """Parse .bib file, extract key, doi, url, title, author, year."""
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    entries = []
    # Split on entry starts
    pattern = r'@(\w+)\s*\{([^,]+),\s*\n(.*?)(?=\n@|\Z)'
    for m in re.finditer(pattern, content, re.DOTALL):
        entry_type = m.group(1).lower()
        if entry_type in ('comment', 'string', 'preamble'):
            continue
        key = m.group(2).strip()
        body = m.group(3)

        def extract_field(name, body):
            # Match field = {value} or field = "value" or field = number
            pat = rf'{name}\s*=\s*(?:\{{((?:[^{{}}]|\{{[^{{}}]*\}})*)\}}|"([^"]*)"|(\d+))'
            fm = re.search(pat, body, re.IGNORECASE)
            if fm:
                return (fm.group(1) or fm.group(2) or fm.group(3) or '').strip()
            return ''

        doi = extract_field('doi', body)
        url = extract_field('url', body)
        title = extract_field('title', body)
        author = extract_field('author', body)
        year = extract_field('year', body)

        # Clean title - remove extra braces
        title = re.sub(r'^\{+|\}+$', '', title)

        entries.append({
            'key': key,
            'type': entry_type,
            'doi': doi,
            'url': url,
            'title': title,
            'author': author,
            'year': year,
            'start': m.start(),
            'end': m.end(),
        })

    return entries


def find_cited_keys(thesis_dir):
    """Find all cited bib keys in .tex files."""
    cited = set()
    tex_files = [f for f in os.listdir(thesis_dir) if f.endswith('.tex')]
    for fname in tex_files:
        path = os.path.join(thesis_dir, fname)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Match \cite{...}, \citep{...}, \citet{...}, \citealp{...}, etc.
        for m in re.finditer(r'\\cite[tp]?\*?\{([^}]+)\}', content):
            keys_str = m.group(1)
            for k in keys_str.split(','):
                k = k.strip()
                if k:
                    cited.add(k)
    return cited


def load_cache():
    """Load DOI verification cache."""
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_cache(cache):
    """Save DOI verification cache."""
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)


def check_doi(doi, cache):
    """Check DOI via CrossRef API. Returns (status, cr_title, cr_year) or (status, None, None)."""
    if doi in cache:
        c = cache[doi]
        return c['status'], c.get('title'), c.get('year')

    url = f'{CROSSREF_API}{urllib.parse.quote(doi, safe="")}?{CROSSREF_MAILTO}'
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'BibVerifier/1.0 (thesis verification; mailto:serhii.korniienko@example.com)')

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            msg = data.get('message', {})
            cr_title = ''
            titles = msg.get('title', [])
            if titles:
                cr_title = titles[0]
            cr_year = ''
            published = msg.get('published-print', msg.get('published-online', {}))
            parts = published.get('date-parts', [[]])
            if parts and parts[0]:
                cr_year = str(parts[0][0])
            cache[doi] = {'status': 200, 'title': cr_title, 'year': cr_year}
            return 200, cr_title, cr_year
    except urllib.error.HTTPError as e:
        cache[doi] = {'status': e.code}
        return e.code, None, None
    except Exception as e:
        cache[doi] = {'status': -1, 'error': str(e)}
        return -1, None, None


def search_doi_by_title(title, author='', year=''):
    """Search CrossRef for a DOI by title. Returns list of (doi, cr_title, score)."""
    query = title
    params = {
        'query.bibliographic': query,
        'rows': '5',
        CROSSREF_MAILTO.split('=')[0]: CROSSREF_MAILTO.split('=')[1],
    }
    url = f'{CROSSREF_API}?{urllib.parse.urlencode(params)}'
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'BibVerifier/1.0 (thesis verification; mailto:serhii.korniienko@example.com)')

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            items = data.get('message', {}).get('items', [])
            results = []
            for item in items:
                cr_doi = item.get('DOI', '')
                cr_titles = item.get('title', [])
                cr_title = cr_titles[0] if cr_titles else ''
                score = item.get('score', 0)
                results.append((cr_doi, cr_title, score))
            return results
    except Exception:
        return []


def title_similarity(t1, t2):
    """Fuzzy title comparison, case-insensitive, ignoring braces/punctuation."""
    def clean(t):
        t = t.lower()
        t = re.sub(r'[{}\[\]"\'`]', '', t)
        t = re.sub(r'\s+', ' ', t).strip()
        return t
    return SequenceMatcher(None, clean(t1), clean(t2)).ratio()


def check_url(url):
    """Check URL with HEAD request. Returns (status_code, redirect_url or None)."""
    req = urllib.request.Request(url, method='HEAD')
    req.add_header('User-Agent', 'Mozilla/5.0 (compatible; BibVerifier/1.0)')
    try:
        with urllib.request.urlopen(req, timeout=15, context=ssl_ctx) as resp:
            return resp.status, resp.url if resp.url != url else None
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        # Try GET as fallback (some servers reject HEAD)
        req2 = urllib.request.Request(url)
        req2.add_header('User-Agent', 'Mozilla/5.0 (compatible; BibVerifier/1.0)')
        try:
            with urllib.request.urlopen(req2, timeout=15, context=ssl_ctx) as resp:
                return resp.status, None
        except urllib.error.HTTPError as e2:
            return e2.code, None
        except Exception as e2:
            return -1, str(e2)


def main():
    print("=== Bibliography Reference Verification ===\n")

    # Step 1: Parse bib
    print("Parsing bibliography...")
    entries = parse_bib(BIB_FILE)
    print(f"  Found {len(entries)} entries")

    # Step 2: Find cited keys
    print("Finding cited keys...")
    cited_keys = find_cited_keys(THESIS_DIR)
    print(f"  Found {len(cited_keys)} cited keys")

    # Classify entries
    bib_keys = {e['key'] for e in entries}
    cited_in_bib = cited_keys & bib_keys
    cited_not_in_bib = cited_keys - bib_keys
    uncited = bib_keys - cited_keys

    has_doi = [e for e in entries if e['doi']]
    has_url = [e for e in entries if e['url']]
    has_both = [e for e in entries if e['doi'] and e['url']]
    has_neither = [e for e in entries if not e['doi'] and not e['url']]

    print(f"\n  Cited & in bib: {len(cited_in_bib)}")
    print(f"  Cited but not in bib: {len(cited_not_in_bib)}")
    if cited_not_in_bib:
        print(f"    Keys: {sorted(cited_not_in_bib)}")
    print(f"  Uncited: {len(uncited)}")
    print(f"  With DOI: {len(has_doi)}")
    print(f"  With URL: {len(has_url)}")
    print(f"  With both: {len(has_both)}")
    print(f"  With neither: {len(has_neither)}")

    # Step 3: Check DOIs
    print("\n--- Checking DOIs via CrossRef ---")
    cache = load_cache()
    doi_entries = [e for e in entries if e['doi']]

    broken_doi_cited = []
    broken_doi_uncited = []
    metadata_mismatches = []
    valid_dois = 0
    error_dois = 0

    for i, entry in enumerate(doi_entries):
        doi = entry['doi']
        key = entry['key']
        is_cited = key in cited_keys

        status, cr_title, cr_year = check_doi(doi, cache)
        time.sleep(REQUEST_DELAY)

        if (i + 1) % 50 == 0:
            print(f"  Checked {i+1}/{len(doi_entries)} DOIs...")
            save_cache(cache)

        if status == 200:
            valid_dois += 1
            # Cross-verify metadata
            if cr_title and entry['title']:
                sim = title_similarity(entry['title'], cr_title)
                if sim < 0.5:
                    metadata_mismatches.append({
                        'key': key,
                        'doi': doi,
                        'bib_title': entry['title'],
                        'cr_title': cr_title,
                        'similarity': sim,
                        'cited': is_cited,
                    })
        elif status == 404:
            rec = {'key': key, 'doi': doi, 'title': entry['title'],
                   'author': entry['author'], 'year': entry['year']}
            if is_cited:
                broken_doi_cited.append(rec)
            else:
                broken_doi_uncited.append(rec)
        else:
            error_dois += 1

    save_cache(cache)
    print(f"\n  Valid DOIs: {valid_dois}")
    print(f"  Broken DOIs (cited): {len(broken_doi_cited)}")
    print(f"  Broken DOIs (uncited): {len(broken_doi_uncited)}")
    print(f"  Metadata mismatches: {len(metadata_mismatches)}")
    print(f"  Errors: {error_dois}")

    # Step 4: Search for correct DOIs for broken cited entries
    print("\n--- Searching correct DOIs for broken cited entries ---")
    corrections = []
    for rec in broken_doi_cited:
        results = search_doi_by_title(rec['title'], rec['author'], rec['year'])
        time.sleep(REQUEST_DELAY * 2)
        best = None
        for cr_doi, cr_title, score in results:
            sim = title_similarity(rec['title'], cr_title)
            if sim > 0.7:
                best = {'doi': cr_doi, 'title': cr_title, 'similarity': sim}
                break
        corrections.append({**rec, 'suggestion': best})
        if best:
            print(f"  {rec['key']}: found {best['doi']} (sim={best['similarity']:.2f})")
        else:
            print(f"  {rec['key']}: no match found")

    # Step 5: Check URLs for cited entries
    print("\n--- Checking URLs for cited entries ---")
    url_entries_cited = [e for e in entries if e['url'] and e['key'] in cited_keys]
    broken_urls = []
    redirect_urls = []
    ok_urls = 0

    for i, entry in enumerate(url_entries_cited):
        url = entry['url']
        status, extra = check_url(url)
        time.sleep(0.1)

        if (i + 1) % 20 == 0:
            print(f"  Checked {i+1}/{len(url_entries_cited)} URLs...")

        if status == 200:
            ok_urls += 1
        elif status in (301, 302):
            redirect_urls.append({'key': entry['key'], 'url': url, 'redirect': extra})
        elif status in (403, 401):
            ok_urls += 1  # paywalled is OK
        elif status in (404, 410):
            broken_urls.append({'key': entry['key'], 'url': url, 'status': status})
        else:
            broken_urls.append({'key': entry['key'], 'url': url, 'status': status, 'error': str(extra)})

    print(f"\n  OK URLs: {ok_urls}")
    print(f"  Broken URLs: {len(broken_urls)}")
    print(f"  Redirects: {len(redirect_urls)}")

    # Step 6: Generate report
    print(f"\n--- Generating report: {REPORT_FILE} ---")
    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("BIBLIOGRAPHY REFERENCE VERIFICATION REPORT\n")
        f.write("=" * 70 + "\n\n")

        f.write(f"Total entries: {len(entries)}\n")
        f.write(f"Cited entries: {len(cited_in_bib)}\n")
        f.write(f"Uncited entries: {len(uncited)}\n")
        f.write(f"Cited but not in bib: {len(cited_not_in_bib)}\n")
        if cited_not_in_bib:
            for k in sorted(cited_not_in_bib):
                f.write(f"  - {k}\n")
        f.write(f"\nDOIs checked: {len(doi_entries)}\n")
        f.write(f"Valid DOIs: {valid_dois}\n")
        f.write(f"Broken DOIs (cited): {len(broken_doi_cited)}\n")
        f.write(f"Broken DOIs (uncited): {len(broken_doi_uncited)}\n")
        f.write(f"Metadata mismatches: {len(metadata_mismatches)}\n")
        f.write(f"API errors: {error_dois}\n\n")

        # Broken cited DOIs with corrections
        f.write("-" * 70 + "\n")
        f.write("BROKEN DOIs — CITED ENTRIES (need fixing)\n")
        f.write("-" * 70 + "\n\n")
        for c in corrections:
            f.write(f"Key: {c['key']}\n")
            f.write(f"  Broken DOI: {c['doi']}\n")
            f.write(f"  Title: {c['title']}\n")
            if c['suggestion']:
                s = c['suggestion']
                f.write(f"  SUGGESTED DOI: {s['doi']}\n")
                f.write(f"  CrossRef title: {s['title']}\n")
                f.write(f"  Similarity: {s['similarity']:.2f}\n")
            else:
                f.write(f"  NO SUGGESTION FOUND\n")
            f.write("\n")

        # Broken uncited DOIs
        f.write("-" * 70 + "\n")
        f.write("BROKEN DOIs — UNCITED ENTRIES (remove from bib)\n")
        f.write("-" * 70 + "\n\n")
        for rec in broken_doi_uncited:
            f.write(f"Key: {rec['key']}\n")
            f.write(f"  DOI: {rec['doi']}\n")
            f.write(f"  Title: {rec['title']}\n\n")

        # Metadata mismatches
        f.write("-" * 70 + "\n")
        f.write("METADATA MISMATCHES (DOI resolves to different paper)\n")
        f.write("-" * 70 + "\n\n")
        for mm in metadata_mismatches:
            f.write(f"Key: {mm['key']} {'[CITED]' if mm['cited'] else '[uncited]'}\n")
            f.write(f"  DOI: {mm['doi']}\n")
            f.write(f"  Bib title: {mm['bib_title']}\n")
            f.write(f"  CR title:  {mm['cr_title']}\n")
            f.write(f"  Similarity: {mm['similarity']:.2f}\n\n")

        # Broken URLs
        f.write("-" * 70 + "\n")
        f.write("BROKEN URLs — CITED ENTRIES\n")
        f.write("-" * 70 + "\n\n")
        for bu in broken_urls:
            f.write(f"Key: {bu['key']}\n")
            f.write(f"  URL: {bu['url']}\n")
            f.write(f"  Status: {bu['status']}\n")
            if 'error' in bu:
                f.write(f"  Error: {bu['error']}\n")
            f.write("\n")

        # Uncited entries list (for potential removal)
        f.write("-" * 70 + "\n")
        f.write(f"UNCITED ENTRIES ({len(uncited)} total)\n")
        f.write("-" * 70 + "\n\n")
        uncited_entries = sorted([e for e in entries if e['key'] in uncited], key=lambda x: x['key'])
        for e in uncited_entries:
            f.write(f"  {e['key']}\n")

        f.write("\n" + "=" * 70 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 70 + "\n")

    # Also save corrections as JSON for automated fixing
    corrections_file = os.path.join(os.path.dirname(__file__), 'doi_corrections.json')
    with open(corrections_file, 'w') as f:
        json.dump({
            'broken_cited': corrections,
            'broken_uncited': [r['key'] for r in broken_doi_uncited],
            'metadata_mismatches': metadata_mismatches,
            'broken_urls': broken_urls,
            'cited_not_in_bib': sorted(cited_not_in_bib),
        }, f, indent=2)
    print(f"  Corrections saved to: {corrections_file}")
    print("\nDone!")


if __name__ == '__main__':
    main()
