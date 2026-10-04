"""Download the latest public ranking and indexing lists, then rebuild the database.

    python update_data.py            # download everything that is missing or stale, then build
    python update_data.py --force    # re-download everything
    python update_data.py --no-build # download only

Schedule: Scimago publishes a new SJR edition every spring, CORE every two years,
Scopus updates its source list monthly, DOAJ and the hijacked-journal list change weekly.
Running this once a year (or after a new SJR edition) keeps PaperLens current. The big
files (SJR, DOAJ, Scopus) are not committed; the small lists are, for reproducibility.
"""
import os
import re
import sys
import time

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_DIR = os.path.join(BASE_DIR, 'data', 'sources')
STALE_AFTER_DAYS = 30

# scimagojr.com rejects non-browser user agents; the others are happy with a plain one.
BROWSER_UA = ('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
              'Chrome/129.0 Safari/537.36')
PLAIN_UA = 'PaperLens/3.0 (https://github.com/aniket02829/paperlens)'

SPJ = 'https://raw.githubusercontent.com/stop-predatory-journals/stop-predatory-journals.github.io/master/_data/'
DOWNLOADS = {
    'sjr.csv': ('https://www.scimagojr.com/journalrank.php?out=xls', BROWSER_UA),
    'core.csv': ('https://portal.core.edu.au/conf-ranks/?search=&by=all&source=all&sort=atitle&page=1&do=Export', PLAIN_UA),
    'doaj.csv': ('https://doaj.org/csv', PLAIN_UA),
    'rw_hijacked.csv': ('https://docs.google.com/spreadsheets/d/1ak985WGOgGbJRJbZFanoktAN_UFeExpE/export?format=csv&gid=5255084', PLAIN_UA),
    'spj_journals.csv': (SPJ + 'journals.csv', PLAIN_UA),
    'spj_publishers.csv': (SPJ + 'publishers.csv', PLAIN_UA),
}
SCOPUS_PAGE = 'https://www.elsevier.com/products/scopus/content'


def download(url, path, user_agent, min_bytes=1000):
    print(f"  {os.path.basename(path):22} <- {url[:80]}")
    headers = {'User-Agent': user_agent, 'Referer': 'https://www.scimagojr.com/journalrank.php'}
    with requests.get(url, headers=headers, stream=True, timeout=600) as response:
        response.raise_for_status()
        tmp = path + '.part'
        with open(tmp, 'wb') as f:
            for chunk in response.iter_content(1 << 16):
                f.write(chunk)
    if os.path.getsize(tmp) < min_bytes:
        os.remove(tmp)
        raise RuntimeError(f"{url} returned only {os.path.getsize(tmp)} bytes")
    os.replace(tmp, path)


def scopus_list_url():
    """The Scopus source list is an xlsx linked from Elsevier's content page; its URL changes monthly."""
    page = requests.get(SCOPUS_PAGE, headers={'User-Agent': BROWSER_UA}, timeout=60).text
    match = re.search(r'https://[^"\s]+ext_list[^"\s]*\.xlsx', page)
    return match.group(0) if match else None


def is_fresh(path):
    return os.path.exists(path) and (time.time() - os.path.getmtime(path)) < STALE_AFTER_DAYS * 86400


def main():
    force = '--force' in sys.argv
    os.makedirs(SOURCES_DIR, exist_ok=True)
    print('Downloading data sources')
    failures = []
    for name, (url, agent) in DOWNLOADS.items():
        path = os.path.join(SOURCES_DIR, name)
        if is_fresh(path) and not force:
            continue
        try:
            download(url, path, agent)
        except Exception as e:  # keep going: a missing list only leaves its table empty
            failures.append(f'{name}: {e}')

    scopus_path = os.path.join(SOURCES_DIR, 'scopus_sources.xlsx')
    if force or not is_fresh(scopus_path):
        try:
            url = scopus_list_url()
            if not url:
                raise RuntimeError('could not find the xlsx link on ' + SCOPUS_PAGE)
            download(url, scopus_path, BROWSER_UA, min_bytes=1_000_000)
        except Exception as e:
            failures.append(f'scopus_sources.xlsx: {e}')

    for failure in failures:
        print(f"[!] {failure}")

    if '--no-build' not in sys.argv:
        print('Building the database')
        import setup_db
        setup_db.build()


if __name__ == '__main__':
    main()
