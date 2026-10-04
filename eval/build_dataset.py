"""
Build the labelled evaluation set: real open-access PDFs whose true venue is known
because of where they were downloaded from.

    python eval/build_dataset.py                 # writes eval/dataset.csv and eval/pdfs/*.pdf
    python eval/build_dataset.py --scale 3       # a larger sample (more papers per venue and quartile)
    python eval/build_dataset.py journals        # rebuild one group only (merged into dataset.csv)
    python eval/build_dataset.py --from-files    # add rows for PDFs already in eval/pdfs/ (named by convention)

Labels come from the source, never from PaperLens itself:
    journal     - publisher PDFs from OpenAlex works in a known SJR journal (quartile from SJR)
    conference  - PDFs from the venue's own archive (ACL Anthology, PMLR, NeurIPS, CVF);
                  rank from CORE
    arxiv       - recent arXiv submissions (preprints at the time of sampling)
"""
import csv
import os
import random
import re
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_DIR = os.path.join(ROOT, 'eval')
PDF_DIR = os.path.join(EVAL_DIR, 'pdfs')
DB_PATH = os.path.join(ROOT, 'data', 'paper_classifier.db')
SEED = 20261003

session = requests.Session()
session.headers['User-Agent'] = 'PaperLens-eval/1.0 (https://github.com/aniket02829/paperlens; research evaluation)'
_last_request = 0.0


def polite_get(url, **kwargs):
    """GET with at most one request per second, so archives are not hammered."""
    global _last_request
    wait = 1.0 - (time.time() - _last_request)
    if wait > 0:
        time.sleep(wait)
    _last_request = time.time()
    return session.get(url, timeout=60, **kwargs)


def download_pdf(url, path):
    if os.path.exists(path) and os.path.getsize(path) > 1000:
        return True
    try:
        response = polite_get(url, allow_redirects=True)
    except requests.RequestException as e:
        print(f'    download failed: {e}')
        return False
    if response.status_code != 200 or b'%PDF' not in response.content[:1024]:
        print(f'    not a PDF ({response.status_code}): {url}')
        return False
    with open(path, 'wb') as f:
        f.write(response.content)
    return True


# ---------------------------------------------------------------- conferences

# (label, acronym, CORE rank, conference type, ACL Anthology prefix, highest paper number, count)
# The count is multiplied by --scale. The *_EXTRA venues are only used when --scale > 1
# and keep their fixed counts.
ACL_VENUES = [
    ('ACL 2023', 'ACL', 'A*', 'International', '2023.acl-long', 900, 3),
    ('EMNLP 2023', 'EMNLP', 'A*', 'International', '2023.emnlp-main', 1000, 3),
    ('NAACL 2024', 'NAACL', 'A', 'International', '2024.naacl-long', 400, 2),
    ('EACL 2024', 'EACL', 'A', 'International', '2024.eacl-long', 150, 2),
    ('COLING 2022', 'COLING', 'B', 'International', '2022.coling-1', 600, 2),
    ('LREC 2022', 'LREC', 'B', 'International', '2022.lrec-1', 700, 2),
    ('CoNLL 2023', 'CoNLL', 'B', 'International', '2023.conll-1', 40, 2),
    ('RANLP 2023', 'RANLP', 'National: bulgaria', 'National', '2023.ranlp-1', 120, 2),
]
ACL_VENUES_EXTRA = [
    ('ACL 2024', 'ACL', 'A*', 'International', '2024.acl-long', 900, 3),
    ('EMNLP 2022', 'EMNLP', 'A*', 'International', '2022.emnlp-main', 800, 3),
    ('NAACL 2022', 'NAACL', 'A', 'International', '2022.naacl-main', 450, 3),
    ('EACL 2023', 'EACL', 'A', 'International', '2023.eacl-main', 250, 3),
    ('LREC-COLING 2024', 'LREC', 'B', 'International', '2024.lrec-main', 1400, 3),
    ('RANLP 2021', 'RANLP', 'National: bulgaria', 'National', '2021.ranlp-1', 180, 3),
]

# (label, acronym, CORE rank, conference type, PMLR volume, how many)
PMLR_VENUES = [
    ('ICML 2023', 'ICML', 'A*', 'International', 'v202', 3),
    ('AISTATS 2023', 'AISTATS', 'A', 'International', 'v206', 2),
    ('UAI 2023', 'UAI', 'A', 'International', 'v216', 2),
    ('ACML 2023', 'ACML', 'C', 'International', 'v222', 2),
    ('COLT 2023', 'COLT', 'A*', 'International', 'v195', 2),
]
PMLR_VENUES_EXTRA = [
    ('ICML 2024', 'ICML', 'A*', 'International', 'v235', 3),
    ('AISTATS 2024', 'AISTATS', 'A', 'International', 'v238', 3),
    ('UAI 2024', 'UAI', 'A', 'International', 'v244', 3),
    ('ALT 2023', 'ALT', 'B', 'International', 'v201', 3),
]

CVF_VENUES = [
    ('CVPR 2023', 'CVPR', 'A*', 'IEEE', 'CVPR2023', 3),
    ('WACV 2024', 'WACV', 'A', 'IEEE', 'WACV2024', 2),
]
CVF_VENUES_EXTRA = [
    ('ICCV 2023', 'ICCV', 'A*', 'IEEE', 'ICCV2023', 3),
    ('CVPR 2024', 'CVPR', 'A*', 'IEEE', 'CVPR2024', 3),
    ('WACV 2023', 'WACV', 'A', 'IEEE', 'WACV2023', 3),
]


def scaled(venues, scale, extra):
    """Base venues with their counts multiplied by scale, then the extra venues (scale > 1 only)."""
    out = [v[:-1] + (v[-1] * scale,) for v in venues]
    if scale > 1:
        out += extra
    return out


def sample_conferences(rng, scale=1):
    rows = []
    for label, acronym, rank, ctype, prefix, highest, count in scaled(ACL_VENUES, scale, ACL_VENUES_EXTRA):
        print(f'  {label}')
        numbers = rng.sample(range(1, highest + 1), count * 2)
        got = 0
        for n in numbers:
            if got == count:
                break
            url = f'https://aclanthology.org/{prefix}.{n}.pdf'
            pid = f'conf-{prefix}.{n}'
            if download_pdf(url, os.path.join(PDF_DIR, f'{pid}.pdf')):
                rows.append(row(pid, url, 'conference', label, acronym, rank, ctype))
                got += 1

    for label, acronym, rank, ctype, volume, count in scaled(PMLR_VENUES, scale, PMLR_VENUES_EXTRA):
        print(f'  {label}')
        page = polite_get(f'https://proceedings.mlr.press/{volume}/').text
        links = sorted(set(re.findall(rf'https://proceedings\.mlr\.press/{volume}/[\w\-]+/[\w\-]+\.pdf', page)))
        links = [l for l in links if 'supp' not in l]
        got = 0
        for url in rng.sample(links, min(len(links), count * 2)):
            if got == count:
                break
            pid = f'conf-pmlr-{volume}-{url.rsplit("/", 1)[1][:-4]}'
            if download_pdf(url, os.path.join(PDF_DIR, f'{pid}.pdf')):
                rows.append(row(pid, url, 'conference', label, acronym, rank, ctype))
                got += 1

    for year, count in [(2023, 3 * scale)] + ([(2022, 3)] if scale > 1 else []):
        print(f'  NeurIPS {year}')
        page = polite_get(f'https://proceedings.neurips.cc/paper_files/paper/{year}').text
        hashes = sorted(set(re.findall(rf'/paper_files/paper/{year}/hash/([0-9a-f]+)-Abstract-Conference\.html', page)))
        got = 0
        for paper_hash in rng.sample(hashes, min(len(hashes), count * 2)):
            if got == count:
                break
            url = f'https://proceedings.neurips.cc/paper_files/paper/{year}/file/{paper_hash}-Paper-Conference.pdf'
            pid = f'conf-neurips{year}-{paper_hash[:10]}'
            if download_pdf(url, os.path.join(PDF_DIR, f'{pid}.pdf')):
                rows.append(row(pid, url, 'conference', f'NeurIPS {year}', 'NeurIPS', 'A*', 'International'))
                got += 1

    for label, acronym, rank, ctype, code, count in scaled(CVF_VENUES, scale, CVF_VENUES_EXTRA):
        print(f'  {label}')
        page = polite_get(f'https://openaccess.thecvf.com/{code}?day=all').text
        links = sorted(set(re.findall(rf'/content/{code}/papers/[\w\-\.]+\.pdf', page)))
        got = 0
        for path in rng.sample(links, min(len(links), count * 2)):
            if got == count:
                break
            url = 'https://openaccess.thecvf.com' + path
            pid = f'conf-{code}-{path.rsplit("/", 1)[1][:40]}'.replace('.pdf', '')
            if download_pdf(url, os.path.join(PDF_DIR, f'{pid}.pdf')):
                rows.append(row(pid, url, 'conference', label, acronym, rank, ctype))
                got += 1
    return rows


# ---------------------------------------------------------------- journals

MAILTO = 'juug25btech29115@jainuniversity.ac.in'


def journal_pdf_candidates(issn, quartile):
    """Yield (paper id, PDF URL) for recent articles in a journal.

    OpenAlex first (it knows the publisher PDF); when it is rate limiting, CrossRef lists
    the journal's recent DOIs and Unpaywall gives each one's open-access PDF.
    """
    try:
        response = polite_get('https://api.openalex.org/works', params={
            'filter': f'primary_location.source.issn:{issn},publication_year:2021-2024,type:article,has_doi:true',
            'per-page': 5, 'select': 'id,doi,primary_location', 'mailto': MAILTO})
        if response.status_code == 200:
            for work in response.json().get('results', []):
                pdf_url = (work.get('primary_location') or {}).get('pdf_url')
                if pdf_url:
                    yield f'journal-{quartile}-{work["id"].rsplit("/", 1)[1]}', pdf_url
            return
    except (requests.RequestException, ValueError):
        pass
    try:
        data = polite_get('https://api.crossref.org/works', params={
            'filter': f'issn:{issn},from-pub-date:2021-01-01,until-pub-date:2024-12-31,type:journal-article',
            'rows': 5, 'select': 'DOI', 'mailto': MAILTO}).json()
    except (requests.RequestException, ValueError):
        return
    for item in (data.get('message') or {}).get('items') or []:
        doi = item.get('DOI')
        try:
            oa = polite_get(f'https://api.unpaywall.org/v2/{doi}', params={'email': MAILTO}).json()
        except (requests.RequestException, ValueError):
            continue
        pdf_url = (oa.get('best_oa_location') or {}).get('url_for_pdf')
        if pdf_url:
            yield f'journal-{quartile}-{re.sub(r"[^A-Za-z0-9]+", "_", doi)[:60]}', pdf_url


def sample_journals(rng, per_quartile=10):
    conn = sqlite3.connect(DB_PATH)
    rows = []
    for quartile in ('Q1', 'Q2', 'Q3', 'Q4'):
        print(f'  journals {quartile}')
        candidates = conn.execute('''
            SELECT title, issn_list, best_quartile FROM journals
            WHERE best_quartile = ? AND open_access = 'Yes' AND issn_list != ''
              AND title NOT LIKE 'Proceedings%'
        ''', (quartile,)).fetchall()
        rng.shuffle(candidates)
        got, used_journals = 0, 0
        for title, issn_list, q in candidates:
            if got >= per_quartile or used_journals > 6 * per_quartile:
                break
            issn = issn_list.split(',')[0].strip()
            issn = f'{issn[:4]}-{issn[4:]}'
            used_journals += 1
            for pid, pdf_url in journal_pdf_candidates(issn, quartile):
                if download_pdf(pdf_url, os.path.join(PDF_DIR, f'{pid}.pdf')):
                    rows.append(row(pid, pdf_url, 'journal', title, issn, q, ''))
                    got += 1
                    break  # one paper per journal, for variety
        print(f'    {got} downloaded')
    return rows


# ---------------------------------------------------------------- preprints

ARXIV_CATEGORIES = ['cs.LG', 'cs.CL', 'cs.CV', 'cs.CR', 'math.CO', 'q-bio.NC', 'physics.optics', 'econ.GN', 'stat.ME']
# Added for the larger sample: more fields outside computer science.
ARXIV_CATEGORIES_EXTRA = ['cs.SE', 'cs.RO', 'stat.ML', 'astro-ph.GA', 'cond-mat.mtrl-sci', 'hep-th', 'math.AP',
                          'q-fin.ST', 'eess.SP', 'physics.med-ph', 'gr-qc', 'q-bio.GN']


def sample_preprints(rng, per_category=3, scale=1):
    rows = []
    for category in ARXIV_CATEGORIES + (ARXIV_CATEGORIES_EXTRA if scale > 1 else []):
        print(f'  arXiv {category}')
        response = polite_get('https://export.arxiv.org/api/query', params={
            'search_query': f'cat:{category}', 'sortBy': 'submittedDate', 'sortOrder': 'descending',
            'start': 0, 'max_results': 40,
        })
        time.sleep(3)  # arXiv asks for 3 seconds between API calls
        root = ET.fromstring(response.content)
        ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}
        entries = []
        for entry in root.findall('atom:entry', ns):
            # Skip papers that already say they were published or accepted somewhere.
            if entry.find('arxiv:journal_ref', ns) is not None or entry.find('arxiv:doi', ns) is not None:
                continue
            comment = (entry.findtext('arxiv:comment', '', ns) or '').lower()
            if any(w in comment for w in ('accepted', 'published', 'to appear', 'camera')):
                continue
            arxiv_id = entry.findtext('atom:id', '', ns).rsplit('/abs/', 1)[-1]
            entries.append(re.sub(r'v\d+$', '', arxiv_id))
        got = 0
        for arxiv_id in rng.sample(entries, min(len(entries), per_category * 2)):
            if got == per_category:
                break
            url = f'https://arxiv.org/pdf/{arxiv_id}'
            pid = f'arxiv-{arxiv_id}'
            if download_pdf(url, os.path.join(PDF_DIR, f'{pid}.pdf')):
                rows.append(row(pid, url, 'arxiv', 'arXiv', category, '', ''))
                got += 1
    return rows


def rows_from_files():
    """Rows for PDFs already in eval/pdfs/ whose names follow the conventions above.

    Lets an interrupted download, or PDFs saved by hand, join the dataset:
    conf-<acl prefix>.<n>, conf-pmlr-<volume>-<id>, conf-<CVF code>-<name>,
    conf-neurips<year>-<hash>, journal-<Q1..Q4>-<anything>, arxiv-<id>.
    """
    acl = {prefix: (label, acronym, rank, ctype) for label, acronym, rank, ctype, prefix, _, _ in ACL_VENUES + ACL_VENUES_EXTRA}
    pmlr = {volume: (label, acronym, rank, ctype) for label, acronym, rank, ctype, volume, _ in PMLR_VENUES + PMLR_VENUES_EXTRA}
    cvf = {code: (label, acronym, rank, ctype) for label, acronym, rank, ctype, code, _ in CVF_VENUES + CVF_VENUES_EXTRA}
    rows = []
    for name in sorted(os.listdir(PDF_DIR)):
        if not name.endswith('.pdf'):
            continue
        pid = name[:-4]
        venue = None
        if pid.startswith('conf-pmlr-'):
            volume = pid.split('-')[2]
            venue = pmlr.get(volume)
            url = f'https://proceedings.mlr.press/{volume}/'
        elif pid.startswith('conf-neurips'):
            year = pid[len('conf-neurips'):][:4]
            venue = (f'NeurIPS {year}', 'NeurIPS', 'A*', 'International')
            url = f'https://proceedings.neurips.cc/paper_files/paper/{year}'
        elif pid.startswith('conf-'):
            rest = pid[5:]
            code = rest.split('-')[0]
            if code in cvf:
                venue, url = cvf[code], f'https://openaccess.thecvf.com/{code}'
            else:
                prefix = rest.rsplit('.', 1)[0]
                venue, url = acl.get(prefix), f'https://aclanthology.org/{rest}.pdf'
        elif pid.startswith('journal-'):
            quartile = pid.split('-')[1]
            rows.append(row(pid, '', 'journal', '', '', quartile, ''))
            continue
        elif pid.startswith('arxiv-'):
            arxiv_id = pid[6:]
            rows.append(row(pid, f'https://arxiv.org/pdf/{arxiv_id}', 'arxiv', 'arXiv', '', '', ''))
            continue
        if venue:
            label, acronym, rank, ctype = venue
            rows.append(row(pid, url, 'conference', label, acronym, rank, ctype))
        else:
            print(f'  skipped {name}: unknown venue')
    return rows


def row(pid, url, category, venue, venue_key, rank, conf_type):
    return {'id': pid, 'url': url, 'expected_category': category, 'expected_venue': venue,
            'venue_key': venue_key, 'expected_rank': rank, 'expected_conference_type': conf_type,
            'sampled_on': time.strftime('%Y-%m-%d')}


def main():
    os.makedirs(PDF_DIR, exist_ok=True)
    args = sys.argv[1:]
    scale = 1
    if '--scale' in args:
        scale = int(args[args.index('--scale') + 1])
        del args[args.index('--scale'):args.index('--scale') + 2]
    rng = random.Random(SEED + scale)
    which = args or ['conferences', 'journals', 'preprints']
    rows = []
    if '--from-files' in which:
        rows += rows_from_files()
        which = [w for w in which if w != '--from-files']
    if 'conferences' in which:
        print('Conferences')
        rows += sample_conferences(rng, scale)
    if 'journals' in which:
        print('Journals')
        rows += sample_journals(rng, per_quartile=10 * scale)
    if 'preprints' in which:
        print('Preprints')
        rows += sample_preprints(rng, scale=scale)

    # Merge with an existing dataset so one group can be (re)built at a time.
    out = os.path.join(EVAL_DIR, 'dataset.csv')
    if os.path.exists(out):
        with open(out, encoding='utf-8') as f:
            existing = {r['id']: r for r in csv.DictReader(f)}
        for r in rows:
            # Freshly sampled rows replace old ones; rows reconstructed from file names
            # (no venue) never overwrite a row that has one.
            if r['id'] not in existing or r['expected_venue'] or not existing[r['id']]['expected_venue']:
                existing[r['id']] = r
        rows = list(existing.values())
    with open(out, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    counts = {}
    for r in rows:
        counts[r['expected_category']] = counts.get(r['expected_category'], 0) + 1
    print(f'Wrote {len(rows)} papers to {out}: {counts}')


if __name__ == '__main__':
    main()
