"""
API fetcher layer for gathering research paper metadata from external APIs.

Sources:
    CrossRef          - the registered metadata behind a DOI (type, venue, ISSN, publisher)
    OpenAlex          - 250M+ works with venue type, DOAJ status, open access and retractions
    Semantic Scholar  - venue type, citations, abstract, and the published DOI of arXiv papers
    arXiv             - title, authors, abstract and subject of preprints (no key, no strict limit)

Every fetch returns {} on failure and never raises, so one slow or broken API
cannot stop a classification.
"""
import difflib
import logging
import re
import threading
import time
import xml.etree.ElementTree as ET
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from classifier.db_base import name_key

logger = logging.getLogger(__name__)

CROSSREF_URL = 'https://api.crossref.org/works'
OPENALEX_URL = 'https://api.openalex.org/works'
S2_URL = 'https://api.semanticscholar.org/graph/v1/paper'
ARXIV_API_URL = 'https://export.arxiv.org/api/query'
ATOM_NS = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}

S2_FIELDS = ('title,venue,publicationVenue,year,citationCount,externalIds,authors,'
             'abstract,fieldsOfStudy,publicationTypes,journal,isOpenAccess,openAccessPdf')
OPENALEX_FIELDS = ('id,doi,display_name,type,publication_year,primary_location,open_access,'
                   'is_retracted,cited_by_count,topics,authorships')
OPENALEX_SOURCES_URL = 'https://api.openalex.org/sources'
OPENALEX_SOURCE_FIELDS = 'id,display_name,type,works_count,cited_by_count,summary_stats,homepage_url,is_in_doaj'
CROSSREF_FIELDS = ('DOI,title,type,container-title,ISSN,publisher,volume,issue,'
                   'published-print,published-online,issued,event,ISBN,author,relation')

# How long to skip an API that answered 429 (rate limited)
DEFAULT_PAUSE_SECONDS = 10
MAX_PAUSE_SECONDS = 15 * 60

# A title search result must be this similar to the query to count as the same paper.
TITLE_MATCH_THRESHOLD = 0.9

ARXIV_STOP_WORDS = frozenset({'and', 'for', 'the', 'with', 'from', 'that', 'this', 'into', 'via', 'using',
                              'based', 'over', 'under', 'between', 'towards', 'toward', 'through', 'about',
                              'our', 'its', 'are', 'can', 'how', 'why', 'what', 'when', 'not', 'new', 'all',
                              'any', 'use', 'per', 'non'})


def titles_match(a: Optional[str], b: Optional[str]) -> bool:
    """True if two titles name the same paper, ignoring case, punctuation and subtitles."""
    key_a, key_b = name_key(a or ''), name_key(b or '')
    if not key_a or not key_b:
        return False
    if key_a == key_b:
        return True
    if difflib.SequenceMatcher(None, key_a, key_b).ratio() >= TITLE_MATCH_THRESHOLD:
        return True
    # PDF titles sometimes lose or gain a subtitle after a colon.
    shorter, longer = sorted((key_a, key_b), key=len)
    return len(shorter) >= 25 and longer.startswith(shorter)


def _first(value):
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _crossref_year(item: Dict) -> Optional[int]:
    published = item.get('published-print') or item.get('published-online') or item.get('issued') or {}
    parts = published.get('date-parts') or [[None]]
    return parts[0][0] if parts and parts[0] else None


class TTLCache:
    """A small thread-safe LRU cache whose entries expire after ttl seconds."""

    def __init__(self, max_size: int = 512, ttl: float = 6 * 3600):
        self.max_size = max_size
        self.ttl = ttl
        self._data: 'OrderedDict[str, tuple]' = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            stored_at, value = entry
            if time.time() - stored_at > self.ttl:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value) -> None:
        with self._lock:
            self._data[key] = (time.time(), value)
            self._data.move_to_end(key)
            while len(self._data) > self.max_size:
                self._data.popitem(last=False)


class MetadataFetcher:
    """Fetches metadata from CrossRef, OpenAlex and Semantic Scholar."""

    # Semantic Scholar allows about one request per second per key, across all threads.
    _s2_lock = threading.Lock()
    _s2_last_call_time = 0.0

    def __init__(self, crossref_email: str, semantic_scholar_api_key: Optional[str] = None,
                 timeout: float = 6, openalex_api_key: Optional[str] = None):
        """
        Initialize the MetadataFetcher.

        Args:
            crossref_email: Email for the CrossRef and OpenAlex polite pools.
            semantic_scholar_api_key: Optional API key for Semantic Scholar.
            timeout: Seconds to wait for each HTTP response.
            openalex_api_key: Optional OpenAlex key. Without one, title searches share a small
                daily budget with everyone on the same IP address.
        """
        self.crossref_email = crossref_email
        self.semantic_scholar_api_key = semantic_scholar_api_key
        self.openalex_api_key = openalex_api_key
        # host -> time until which we skip that API because it said we were rate limited
        self._cooldown_until: Dict[str, float] = {}
        self.timeout = timeout
        self.cache = TTLCache()

        self.session = requests.Session()
        # 429s are not retried here: an API can ask us to wait for hours (OpenAlex sends
        # Retry-After: 46000 once its daily budget is spent), so _get_json pauses that
        # source for a bounded time instead and the other sources carry on.
        retry = Retry(total=2, backoff_factor=0.5, status_forcelist=(500, 502, 503, 504),
                      allowed_methods=('GET',), respect_retry_after_header=False)
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=20)
        self.session.mount('https://', adapter)
        user_agent = 'PaperLens/3.0 (https://github.com/aniket02829/paperlens'
        user_agent += f'; mailto:{crossref_email})' if crossref_email else ')'
        self.session.headers['User-Agent'] = user_agent

    # ------------------------------------------------------------------ HTTP

    def _get_json(self, url: str, params: Optional[Dict] = None,
                  headers: Optional[Dict] = None, label: str = '') -> Optional[Dict]:
        """GET a JSON document, caching successes. Returns None on any failure."""
        cache_key = url + '?' + '&'.join(f'{k}={v}' for k, v in sorted((params or {}).items()))
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        host = url.split('/')[2]
        if time.time() < self._cooldown_until.get(host, 0):
            return None
        try:
            response = self.session.get(url, params=params, headers=headers, timeout=self.timeout)
            if response.status_code == 429:
                self._pause_source(host, response.headers.get('Retry-After'))
                return None
            if response.status_code == 404:
                self.cache.set(cache_key, {})
                return None
            response.raise_for_status()
            data = response.json()
            self.cache.set(cache_key, data)
            return data
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.warning(f"{label or url} request failed: {e}")
            return None

    def _pause_source(self, host: str, retry_after: Optional[str]) -> None:
        """Skip a rate-limited API for a while, never longer than MAX_PAUSE_SECONDS."""
        try:
            wait = float(retry_after) if retry_after else DEFAULT_PAUSE_SECONDS
        except ValueError:
            wait = DEFAULT_PAUSE_SECONDS
        wait = max(1.0, min(wait, MAX_PAUSE_SECONDS))
        self._cooldown_until[host] = time.time() + wait
        logger.warning(f"{host} is rate limiting us; skipping it for {int(wait)}s")

    # ------------------------------------------------------------------ CrossRef

    def _parse_crossref_item(self, item: Dict) -> Dict[str, Any]:
        authors = [
            ' '.join(filter(None, [a.get('given'), a.get('family')])) or a.get('name')
            for a in item.get('author') or []
        ]
        result = {
            'doi': item.get('DOI'),
            'title': _first(item.get('title')),
            'type': item.get('type'),
            'container-title': _first(item.get('container-title')),
            'issn': list(item.get('ISSN') or []),
            'isbn': list(item.get('ISBN') or []),
            'publisher': item.get('publisher'),
            'volume': item.get('volume'),
            'issue': item.get('issue'),
            'year': _crossref_year(item),
            'event': (item.get('event') or {}).get('name'),
            'authors': ', '.join(a for a in authors if a) or None,
        }
        return {k: v for k, v in result.items() if v not in (None, [], '')}

    def fetch_by_doi(self, doi: str) -> Dict[str, Any]:
        """Fetch CrossRef metadata for a DOI. Returns {} if CrossRef has no record."""
        logger.info(f"Fetching CrossRef metadata for DOI: {doi}")
        data = self._get_json(f'{CROSSREF_URL}/{doi}', label='CrossRef DOI')
        if not data or not data.get('message'):
            return {}
        return self._parse_crossref_item(data['message'])

    def fetch_by_title(self, title: str) -> Dict[str, Any]:
        """Search CrossRef by title. Returns the best match only if its title really matches.

        A paper often exists twice: as a preprint (SSRN, Research Square...) and as the
        published article. The published record wins; a lone preprint record is followed
        to its published version when CrossRef links them ('is-preprint-of').
        """
        logger.info(f"Searching CrossRef by title: {title[:80]}")
        params = {'query.bibliographic': title, 'rows': 5, 'select': CROSSREF_FIELDS}
        data = self._get_json(CROSSREF_URL, params=params, label='CrossRef title search')
        items = ((data or {}).get('message') or {}).get('items') or []
        matches = [item for item in items if titles_match(title, _first(item.get('title')))]
        for item in matches:
            if item.get('type') != 'posted-content':
                return self._parse_crossref_item(item)
        for item in matches:
            published = ((item.get('relation') or {}).get('is-preprint-of') or [{}])[0].get('id')
            if published:
                record = self.fetch_by_doi(published)
                if record:
                    return record
        return self._parse_crossref_item(matches[0]) if matches else {}

    # ------------------------------------------------------------------ OpenAlex

    def _parse_openalex_work(self, work: Dict) -> Dict[str, Any]:
        location = work.get('primary_location') or {}
        source = location.get('source') or {}
        open_access = work.get('open_access') or {}
        topics = work.get('topics') or []
        authors = [((a.get('author') or {}).get('display_name')) for a in work.get('authorships') or []]
        result = {
            'id': work.get('id'),
            'doi': (work.get('doi') or '').replace('https://doi.org/', '') or None,
            'title': work.get('display_name'),
            'type': work.get('type'),
            'year': work.get('publication_year'),
            'source_name': source.get('display_name') or location.get('raw_source_name'),
            'source_id': source.get('id'),
            'source_type': source.get('type'),
            'raw_type': location.get('raw_type'),
            'issn_l': source.get('issn_l'),
            'issn': list(source.get('issn') or []),
            'is_in_doaj': source.get('is_in_doaj'),
            'publisher': source.get('host_organization_name'),
            'is_oa': open_access.get('is_oa'),
            'oa_url': open_access.get('oa_url'),
            'is_retracted': bool(work.get('is_retracted')),
            'cited_by_count': work.get('cited_by_count'),
            'topics': [t.get('display_name') for t in topics[:3] if t.get('display_name')],
            'subfield': ((topics[0].get('subfield') or {}).get('display_name')) if topics else None,
            'field': ((topics[0].get('field') or {}).get('display_name')) if topics else None,
            'authors': ', '.join(a for a in authors if a) or None,
        }
        return {k: v for k, v in result.items() if v not in (None, [], '')}

    def _openalex_params(self, extra: Optional[Dict] = None) -> Dict:
        params = {'select': OPENALEX_FIELDS}
        if self.openalex_api_key:
            params['api_key'] = self.openalex_api_key
        elif self.crossref_email:
            params['mailto'] = self.crossref_email
        params.update(extra or {})
        return params

    def fetch_openalex(self, doi: str) -> Dict[str, Any]:
        """Fetch an OpenAlex work by DOI."""
        logger.info(f"Fetching OpenAlex work for DOI: {doi}")
        data = self._get_json(f'{OPENALEX_URL}/doi:{doi}', params=self._openalex_params(),
                              label='OpenAlex DOI')
        return self._parse_openalex_work(data) if data else {}

    def fetch_openalex_by_title(self, title: str) -> Dict[str, Any]:
        """Search OpenAlex by title. Returns the best match only if its title really matches."""
        logger.info(f"Searching OpenAlex by title: {title[:80]}")
        params = self._openalex_params({'search': title, 'per-page': 5})
        data = self._get_json(OPENALEX_URL, params=params, label='OpenAlex title search')
        matches = [self._parse_openalex_work(work) for work in (data or {}).get('results') or []
                   if titles_match(title, work.get('display_name'))]
        # Prefer the published record over a preprint copy of the same paper.
        for work in matches:
            if work.get('source_type') != 'repository' and work.get('type') != 'preprint':
                return work
        return matches[0] if matches else {}

    def fetch_openalex_source(self, source_id: str) -> Dict[str, Any]:
        """Citation statistics for a venue (journal or proceedings) from OpenAlex.

        Used when a venue is in neither Scimago nor CORE, so the reader still gets
        a measure of its impact. OpenAlex's h-index and 2-year mean citedness are
        computed the same way as SJR's h-index and Scopus's CiteScore-style ratio.
        """
        short_id = (source_id or '').rsplit('/', 1)[-1]
        if not short_id.startswith('S'):
            return {}
        params = {'select': OPENALEX_SOURCE_FIELDS}
        if self.openalex_api_key:
            params['api_key'] = self.openalex_api_key
        elif self.crossref_email:
            params['mailto'] = self.crossref_email
        data = self._get_json(f'{OPENALEX_SOURCES_URL}/{short_id}', params=params, label='OpenAlex source')
        if not data:
            return {}
        stats = data.get('summary_stats') or {}
        result = {
            'name': data.get('display_name'),
            'type': data.get('type'),
            'works_count': data.get('works_count'),
            'cited_by_count': data.get('cited_by_count'),
            'h_index': stats.get('h_index'),
            'i10_index': stats.get('i10_index'),
            'mean_citedness_2yr': round(stats['2yr_mean_citedness'], 2) if stats.get('2yr_mean_citedness') is not None else None,
            'homepage_url': data.get('homepage_url'),
            'is_in_doaj': data.get('is_in_doaj'),
        }
        return {k: v for k, v in result.items() if v is not None}

    # ------------------------------------------------------------------ Semantic Scholar

    def fetch_semantic_scholar(self, identifier: str) -> Dict[str, Any]:
        """
        Fetch metadata from Semantic Scholar.

        Args:
            identifier: A DOI ('10.x/...'), 'arXiv:<id>', or a Semantic Scholar paper ID.
        """
        if identifier.lower().startswith('arxiv:'):
            query_id = f"ARXIV:{identifier[6:]}"
        elif identifier.startswith('10.'):
            query_id = f"DOI:{identifier}"
        else:
            query_id = identifier

        url = f'{S2_URL}/{query_id}'
        params = {'fields': S2_FIELDS}
        cache_key = url + '?' + f"fields={S2_FIELDS}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        headers = {}
        if self.semantic_scholar_api_key:
            headers['x-api-key'] = self.semantic_scholar_api_key

        with MetadataFetcher._s2_lock:
            elapsed = time.time() - MetadataFetcher._s2_last_call_time
            if elapsed < 1.05:
                time.sleep(1.05 - elapsed)
            MetadataFetcher._s2_last_call_time = time.time()

        logger.info(f"Fetching Semantic Scholar metadata for: {query_id}")
        return self._get_json(url, params=params, headers=headers, label='Semantic Scholar') or {}

    # ------------------------------------------------------------------ arXiv

    def _arxiv_query(self, params: Dict, label: str) -> list:
        """Run an arXiv API query and return its Atom entries (cached)."""
        cache_key = ARXIV_API_URL + '?' + '&'.join(f'{k}={v}' for k, v in sorted(params.items()))
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached
        logger.info(f"{label}: {params}")
        try:
            response = self.session.get(ARXIV_API_URL, params=params, timeout=self.timeout)
            response.raise_for_status()
            root = ET.fromstring(response.content)
        except (requests.exceptions.RequestException, ET.ParseError) as e:
            logger.warning(f"arXiv request failed: {e}")
            return []
        entries = [self._parse_arxiv_entry(e) for e in root.findall('atom:entry', ATOM_NS)]
        entries = [e for e in entries if e]
        self.cache.set(cache_key, entries)
        return entries

    @staticmethod
    def _parse_arxiv_entry(entry) -> Dict[str, Any]:
        entry_id = entry.findtext('atom:id', '', ATOM_NS)
        if 'arxiv.org/abs/' not in entry_id:
            return {}

        def text(path):
            value = entry.findtext(path, None, ATOM_NS)
            return ' '.join(value.split()) if value else None

        primary = entry.find('arxiv:primary_category', ATOM_NS)
        published = text('atom:published') or ''
        result = {
            'arxiv_id': entry_id.rsplit('/abs/', 1)[1],
            'title': text('atom:title'),
            'abstract': text('atom:summary'),
            'authors': ', '.join(a.findtext('atom:name', '', ATOM_NS) for a in entry.findall('atom:author', ATOM_NS)) or None,
            'year': int(published[:4]) if published[:4].isdigit() else None,
            'primary_category': primary.get('term') if primary is not None else None,
            'doi': text('arxiv:doi'),
            'journal_ref': text('arxiv:journal_ref'),
        }
        return {k: v for k, v in result.items() if v}

    def fetch_arxiv(self, arxiv_id: str) -> Dict[str, Any]:
        """Fetch a preprint's record from the arXiv API (Atom XML)."""
        entries = self._arxiv_query({'id_list': arxiv_id}, 'Fetching arXiv record')
        return entries[0] if entries else {}

    def fetch_arxiv_by_title(self, title: str) -> Dict[str, Any]:
        """Find a preprint on arXiv by its title (for PDFs that carry no arXiv stamp).

        Returns the record only if the title really matches, like the other title searches.
        """
        # Stop words make arXiv's ti: search return nothing, so only content words are sent.
        words = [w for w in re.findall(r'[A-Za-z0-9]+', title)
                 if len(w) > 2 and w.lower() not in ARXIV_STOP_WORDS][:6]
        if len(words) < 3:
            return {}
        query = ' AND '.join(f'ti:{w}' for w in words)
        for entry in self._arxiv_query({'search_query': query, 'max_results': 5}, 'Searching arXiv by title'):
            if titles_match(title, entry.get('title')):
                return entry
        return {}

    # ------------------------------------------------------------------ Combined

    def gather(self, doi: Optional[str] = None, arxiv_id: Optional[str] = None,
               title: Optional[str] = None) -> Dict[str, Any]:
        """
        Query every source that can help, in parallel where possible.

        Returns {'crossref': {...}, 'openalex': {...}, 's2': {...}, 'arxiv': {...},
                 'published_doi': str|None, 'matched_by': 'doi'|'arxiv'|'title'|None}.
        published_doi is set when an arXiv paper turns out to have a published version.
        """
        out = {'crossref': {}, 'openalex': {}, 's2': {}, 'arxiv': {}, 'published_doi': None, 'matched_by': None}

        with ThreadPoolExecutor(max_workers=3) as pool:
            if doi and not doi.lower().startswith('10.48550/arxiv.'):
                out['matched_by'] = 'doi'
                crossref = pool.submit(self.fetch_by_doi, doi)
                openalex = pool.submit(self.fetch_openalex, doi)
                s2 = pool.submit(self.fetch_semantic_scholar, doi)
                out['crossref'], out['openalex'], out['s2'] = crossref.result(), openalex.result(), s2.result()
                if out['crossref'] or out['openalex'] or out['s2']:
                    return out
                # The DOI didn't resolve (often a DOI misread from the PDF): try the title instead.
                out['matched_by'] = None

            if arxiv_id and not out['matched_by']:
                s2 = pool.submit(self.fetch_semantic_scholar, f'arXiv:{arxiv_id}')
                arxiv = pool.submit(self.fetch_arxiv, arxiv_id)
                out['s2'], out['arxiv'] = s2.result(), arxiv.result()
                if out['s2'] or out['arxiv']:
                    out['matched_by'] = 'arxiv'
                published_doi = (out['s2'].get('externalIds') or {}).get('DOI') or out['arxiv'].get('doi')
                if published_doi and not published_doi.lower().startswith('10.48550/'):
                    out['published_doi'] = published_doi
                    crossref = pool.submit(self.fetch_by_doi, published_doi)
                    openalex = pool.submit(self.fetch_openalex, published_doi)
                    out['crossref'], out['openalex'] = crossref.result(), openalex.result()
                elif out['arxiv'].get('title'):
                    # Gives the subject (for journal suggestions) and sometimes a published copy.
                    out['openalex'] = self.fetch_openalex_by_title(out['arxiv']['title'])
                return out

            if title and len(title) >= 10:
                crossref = pool.submit(self.fetch_by_title, title)
                openalex = pool.submit(self.fetch_openalex_by_title, title)
                out['crossref'], out['openalex'] = crossref.result(), openalex.result()
                found_doi = out['crossref'].get('doi') or out['openalex'].get('doi')
                if found_doi:
                    out['matched_by'] = 'title'
                    if not out['crossref']:
                        out['crossref'] = self.fetch_by_doi(found_doi)
                    if not out['openalex']:
                        out['openalex'] = self.fetch_openalex(found_doi)
                    out['s2'] = self.fetch_semantic_scholar(found_doi)
                elif out['openalex']:
                    out['matched_by'] = 'title'
                else:
                    # Nothing registered under this title: it may be a preprint whose PDF
                    # carries no arXiv stamp. arXiv's own search settles that.
                    arxiv = self.fetch_arxiv_by_title(title)
                    if arxiv:
                        out['arxiv'] = arxiv
                        out['matched_by'] = 'title'
                        published_doi = arxiv.get('doi')
                        if published_doi and not published_doi.lower().startswith('10.48550/'):
                            out['published_doi'] = published_doi
                            out['crossref'] = self.fetch_by_doi(published_doi)
                            out['openalex'] = self.fetch_openalex(published_doi)
        return out
