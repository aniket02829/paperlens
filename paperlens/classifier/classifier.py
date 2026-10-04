"""
Core classifier engine for research paper classification.

This module ties together the PDF/DOCX parsers, metadata fetcher, journal DB,
and conference DB to produce a final classification for an uploaded paper or
for a DOI / arXiv ID / title typed in by the user.
"""
import re
import logging
from typing import Dict, Any, List, Optional

from classifier.pdf_parser import PDFParser
from classifier.docx_parser import DocxParser
from classifier.metadata_fetcher import MetadataFetcher, titles_match
from classifier.journal_db import JournalDB
from classifier.conference_db import ConferenceDB
from classifier.venue_checks import VenueChecksDB
from classifier import text_metadata

logger = logging.getLogger(__name__)

JOURNAL, CONFERENCE, PREPRINT = 'journal', 'conference', 'arxiv'

# Uppercase words in venue names that are publishers or societies, not conference acronyms.
NOT_ACRONYMS = {'IEEE', 'ACM', 'CVF', 'IEEE/CVF', 'IFIP', 'LNCS', 'SPIE', 'AIP', 'IET', 'ICPS',
                'SIAM', 'USA', 'UK', 'EU', 'PMLR', 'CEUR', 'II', 'III', 'IV', 'VI'}
CONFERENCE_WORDS = ('conference', 'proceedings', 'symposium', 'workshop', 'lecture notes', 'congress')
BOOK_SERIES_WORDS = ('lecture notes', 'communications in computer and information science',
                     'advances in intelligent systems', 'smart innovation', 'book series')
CONFERENCE_LINE = re.compile(r'\b(proceedings|conference|symposium|workshop|annual meeting|congress)\b', re.IGNORECASE)
NATIONAL_KEYWORDS = ('national conference', 'national symposium', 'national workshop',
                     'all-india', 'all india', 'national convention', 'national seminar')

# arXiv subject classes mapped to the closest Scopus/SJR category, for journal suggestions.
ARXIV_TO_SJR_CATEGORY = [
    ('cs.CV', 'Computer Vision and Pattern Recognition'), ('eess.IV', 'Computer Vision and Pattern Recognition'),
    ('cs.CL', 'Artificial Intelligence'), ('cs.AI', 'Artificial Intelligence'), ('cs.LG', 'Artificial Intelligence'),
    ('stat.ML', 'Artificial Intelligence'), ('cs.NE', 'Artificial Intelligence'), ('cs.IR', 'Information Systems'),
    ('cs.DB', 'Information Systems'), ('cs.CR', 'Computer Networks and Communications'),
    ('cs.NI', 'Computer Networks and Communications'), ('cs.SE', 'Software'), ('cs.PL', 'Software'),
    ('cs.RO', 'Control and Systems Engineering'), ('eess.SY', 'Control and Systems Engineering'),
    ('cs.HC', 'Human-Computer Interaction'), ('cs.DS', 'Theoretical Computer Science'),
    ('cs.CC', 'Theoretical Computer Science'), ('cs.DC', 'Computer Networks and Communications'),
    ('eess.SP', 'Signal Processing'), ('eess.AS', 'Signal Processing'), ('cs.SD', 'Signal Processing'),
    ('cs', 'Computer Science (miscellaneous)'), ('math', 'Mathematics (miscellaneous)'), ('stat', 'Statistics and Probability'),
    ('quant-ph', 'Atomic and Molecular Physics, and Optics'), ('astro-ph', 'Astronomy and Astrophysics'),
    ('cond-mat', 'Condensed Matter Physics'), ('hep', 'Nuclear and High Energy Physics'), ('physics', 'Physics and Astronomy (miscellaneous)'),
    ('q-bio', 'Biochemistry, Genetics and Molecular Biology (miscellaneous)'), ('q-fin', 'Finance'),
    ('econ', 'Economics and Econometrics'),
]

DOI_IN_TEXT = re.compile(r'(10\.\d{4,9}/\S+)', re.IGNORECASE)
ARXIV_URL = re.compile(r'arxiv\.org/(?:abs|pdf)/([^\s?#]+?)(?:\.pdf)?(?:[?#]|$)', re.IGNORECASE)
ARXIV_BARE = re.compile(r'^(?:arxiv\s*:\s*)?(\d{4}\.\d{4,5}(?:v\d+)?|[a-z\-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)$', re.IGNORECASE)


class Signals:
    """The evidence behind a classification.

    messages are shown to the user; keys feed the confidence score, so rewording
    a message never changes the confidence.
    """

    def __init__(self):
        self.messages: List[str] = []
        self.keys: set = set()

    def add(self, key: str, message: str) -> None:
        self.keys.add(key)
        self.messages.append(message)


def parse_identifier(query: str) -> Dict[str, Optional[str]]:
    """Work out whether a search box query is a DOI, an arXiv ID/URL, or a title."""
    query = (query or '').strip()
    out = {'doi': None, 'arxiv_id': None, 'title': None}
    if not query:
        return out

    arxiv_url = ARXIV_URL.search(query)
    arxiv_bare = ARXIV_BARE.match(query)
    doi_match = DOI_IN_TEXT.search(query)
    if arxiv_url:
        out['arxiv_id'] = arxiv_url.group(1)
    elif arxiv_bare:
        out['arxiv_id'] = arxiv_bare.group(1)
    elif doi_match:
        doi = text_metadata.clean_doi(doi_match.group(1))
        arxiv_doi = text_metadata.ARXIV_DOI_PATTERN.match(doi)
        if arxiv_doi:
            out['arxiv_id'] = arxiv_doi.group(1)
        else:
            out['doi'] = doi
    else:
        out['title'] = ' '.join(query.split())
    return out


def clean_venue_name(name: str) -> str:
    """'Proceedings of the 2016 IEEE Conference on X (CVPR)' -> 'IEEE Conference on X'."""
    name = re.sub(r'\([^)]*\)', ' ', name or '')
    name = re.sub(r'\b(19|20)\d{2}\b', ' ', name)
    name = re.sub(r'\b\d+(st|nd|rd|th)\b', ' ', name, flags=re.IGNORECASE)
    name = re.sub(r'^\s*(proceedings of( the)?|proc\. of( the)?)\s+', '', name.strip(), flags=re.IGNORECASE)
    return ' '.join(name.split())


def acronym_candidates(*names: str) -> List[str]:
    """Pull likely conference acronyms (CVPR, NeurIPS, ICSE'23) out of venue names."""
    found: List[str] = []
    for name in names:
        if not name:
            continue
        tokens = re.findall(r'\(([A-Za-z][A-Za-z0-9\-]{1,14})\)', name)
        tokens += re.findall(r"\b([A-Z][A-Za-z]*[A-Z][A-Za-z0-9]*)(?:['’]?\d{2,4})?\b", name)
        for token in tokens:
            token = re.sub(r"['’]?\d{2,4}$", '', token)
            if len(token) >= 2 and token.upper() not in NOT_ACRONYMS and token not in found:
                found.append(token)
    return found


class PaperClassifier:
    """
    Main classification engine that analyzes a research paper and determines:
    - Whether it's a journal paper, conference paper, or arXiv preprint
    - If Journal: which quartile (Q1-Q4), SJR score, journal name
    - If Conference: whether it's IEEE, International, or National + CORE rank
    - If arXiv: suggests suitable journals for publication
    """

    def __init__(self, db_path: str, crossref_email: str,
                 semantic_scholar_api_key: Optional[str] = None,
                 openalex_api_key: Optional[str] = None):
        """
        Initialize the classifier with all required components.

        Args:
            db_path: Path to the SQLite database containing journal/conference data.
            crossref_email: Email for CrossRef and OpenAlex polite pools.
            semantic_scholar_api_key: Optional Semantic Scholar API key.
            openalex_api_key: Optional OpenAlex API key.
        """
        self.pdf_parser = PDFParser()
        self.docx_parser = DocxParser()
        self.fetcher = MetadataFetcher(crossref_email, semantic_scholar_api_key,
                                       openalex_api_key=openalex_api_key)
        self.journal_db = JournalDB(db_path)
        self.conference_db = ConferenceDB(db_path)
        self.checks = VenueChecksDB(db_path)

    # ================================================================== entry points

    def classify(self, file_path: str) -> Dict[str, Any]:
        """Classify a research paper from an uploaded PDF or DOCX file."""
        if file_path.lower().endswith('.pdf'):
            parsed = self.pdf_parser.parse(file_path)
        elif file_path.lower().endswith('.docx'):
            parsed = self.docx_parser.parse(file_path)
        else:
            return self._error_result("Unsupported file format. Please upload a PDF or DOCX file.")

        if parsed.get('looks_scanned'):
            return self._error_result(
                "This PDF is a scanned image: its pages are pictures, so the text cannot be read. "
                "Please search by the paper's DOI or title instead."
            )
        if not parsed.get('full_text', '').strip():
            return self._error_result(
                "Could not extract text from the document. It may be a scanned image or a damaged file. "
                "Try typing the paper's DOI or title instead."
            )
        return self._classify_parsed(parsed, from_file=True)

    def lookup(self, query: str) -> Dict[str, Any]:
        """Classify a paper from a DOI, a DOI or arXiv link, an arXiv ID, or a title."""
        identifier = parse_identifier(query)
        if not any(identifier.values()):
            return self._error_result("Please enter a DOI, an arXiv ID or link, or the paper's title.")
        if identifier['title'] and len(identifier['title']) < 10:
            return self._error_result("That title is too short to search for. Please enter the full title.")

        parsed = text_metadata.empty_result()
        parsed.update({k: v for k, v in identifier.items() if v})
        parsed['page_count'] = None
        result = self._classify_parsed(parsed, from_file=False)
        if result['category'] == 'unknown' and not result.get('matched_by'):
            result['error'] = ("We couldn't find this paper in CrossRef, OpenAlex or Semantic Scholar. "
                               "Check the spelling, or try the DOI instead of the title.")
        return result

    # ================================================================== pipeline

    def _classify_parsed(self, parsed: Dict[str, Any], from_file: bool) -> Dict[str, Any]:
        signals = Signals()

        arxiv_id = parsed.get('arxiv_id')
        is_arxiv = bool(arxiv_id or parsed.get('has_arxiv_stamp'))
        if is_arxiv:
            signals.add('arxiv_id', f"arXiv ID detected: {arxiv_id or 'stamp found'}")

        doi = parsed.get('doi')
        if doi:
            signals.add('doi', f"DOI found: {doi}")

        meta = self.fetcher.gather(doi=doi, arxiv_id=arxiv_id, title=parsed.get('title'))
        crossref, openalex, s2 = meta['crossref'], meta['openalex'], meta['s2']
        s2_venue = s2.get('publicationVenue') or {}

        arxiv_by_title = False
        if not is_arxiv and meta['arxiv'].get('arxiv_id'):
            # Found on arXiv by title. The PDF itself carries no arXiv stamp, so this may be
            # the published copy of a paper that also exists on arXiv: the paper's own text
            # (a proceedings footer, a journal header) is allowed to outweigh it.
            is_arxiv = arxiv_by_title = True
            arxiv_id = meta['arxiv']['arxiv_id']
            parsed['arxiv_id'] = arxiv_id
            signals.add('arxiv_title_match', f"Found on arXiv by title: {arxiv_id}")
        elif meta['matched_by'] == 'title':
            signals.add('title_match', "Paper matched by its title in CrossRef/OpenAlex")
        if meta['published_doi']:
            signals.add('published_version', f"Published version found (DOI {meta['published_doi']})")
        if crossref.get('type'):
            signals.add('crossref_type', f"CrossRef type: {crossref['type']}")
        if openalex.get('source_type') or openalex.get('type'):
            signals.add('openalex_type', f"OpenAlex type: {openalex.get('type', 'unknown')}"
                        + (f" in a {openalex['source_type']}" if openalex.get('source_type') else ''))
        if s2.get('venue'):
            signals.add('s2_venue', f"Semantic Scholar venue: {s2['venue']}")
        if s2_venue.get('type'):
            signals.add('s2_type', f"S2 venue type: {s2_venue['type']}")

        if from_file and crossref.get('title') and parsed.get('title') and not titles_match(crossref['title'], parsed['title']):
            signals.add('title_mismatch', "Note: the DOI's registered title differs from the title read from the file")

        api_votes = self._api_votes(crossref, openalex, s2)
        text_journal = self._journal_named_in_text(parsed) if from_file else None
        text_votes = self._text_votes(parsed, signals, text_journal) if from_file else {JOURNAL: 0, CONFERENCE: 0}

        venue_name = (
            crossref.get('container-title') or
            openalex.get('source_name') or
            (s2.get('venue') if 'arxiv' not in (s2.get('venue') or '').lower() else None) or
            parsed.get('venue') or
            ''
        )

        category = self._decide(is_arxiv, api_votes, text_votes, weak_arxiv=arxiv_by_title)
        if category == JOURNAL:
            result = self._classify_journal(parsed, meta, venue_name, signals, text_journal)
        elif category == CONFERENCE:
            result = self._classify_conference(parsed, meta, venue_name, signals)
        elif category == PREPRINT:
            result = self._classify_arxiv(parsed, meta, signals)
        else:
            signals.add('unknown', "Could not determine paper type with sufficient confidence")
            result = self._base_result(parsed, meta, 'unknown')
            result['venue'] = venue_name or 'Unknown'

        if is_arxiv and category in (JOURNAL, CONFERENCE):
            result['is_arxiv'] = True
            result['arxiv_id'] = arxiv_id
            signals.add('also_arxiv', "Paper is also available on arXiv")

        if category in (JOURNAL, CONFERENCE, 'unknown'):
            self._venue_checks(result, parsed, meta, venue_name, signals)

        result['signals'] = signals.messages
        result['confidence'] = self._calculate_confidence(category, api_votes, text_votes, signals, result)
        result['trust'] = self._trust_check(result, openalex)
        return result

    # ================================================================== venue checks

    @staticmethod
    def _collect_issns(parsed: Dict, meta: Dict) -> List[str]:
        crossref, openalex, s2 = meta['crossref'], meta['openalex'], meta['s2']
        s2_venue = s2.get('publicationVenue') or {}
        issns = list(crossref.get('issn', [])) + list(openalex.get('issn', []))
        if openalex.get('issn_l'):
            issns.append(openalex['issn_l'])
        for issn in (parsed.get('issn'), s2_venue.get('issn')):
            if issn:
                issns.append(issn)
        return list(dict.fromkeys(issns))

    def _venue_checks(self, result: Dict, parsed: Dict, meta: Dict, venue_name: str, signals: Signals) -> None:
        """Indexing status and reputation warnings for the venue, from the public lists."""
        crossref, openalex, s2 = meta['crossref'], meta['openalex'], meta['s2']
        s2_venue = s2.get('publicationVenue') or {}
        issns = self._collect_issns(parsed, meta)
        names = [result.get('venue'), venue_name, crossref.get('container-title'), openalex.get('source_name'),
                 s2_venue.get('name'), parsed.get('venue')]
        names = [n for n in dict.fromkeys(names) if n and n.lower() not in ('unknown journal', 'unknown conference', 'unknown')]
        publishers = [result.get('publisher'), crossref.get('publisher'), openalex.get('publisher')]

        if result['category'] == JOURNAL or (result['category'] == 'unknown' and issns):
            result['scopus'] = self.checks.scopus(issns, names)
            result['doaj'] = self.checks.doaj(issns, names)
            if result['scopus']:
                if result['scopus']['discontinued']:
                    year = result['scopus'].get('discontinued_year')
                    signals.add('scopus_discontinued', "Scopus discontinued this journal" + (f" in {year}" if year else ''))
                elif result['scopus']['active']:
                    signals.add('scopus_active', "Journal is on the Scopus source list (active)")
            if result['doaj']:
                signals.add('doaj', "Journal is listed in DOAJ")

        hijacked = self.checks.hijacked(issns, names)
        predatory = self.checks.predatory(names, publishers)
        result['watchlist'] = {'hijacked': hijacked, 'predatory_journal': predatory['journal'],
                               'predatory_publisher': predatory['publisher']}
        if hijacked:
            signals.add('hijacked', "A hijacked (fake) copy of this journal exists; check the website")
        if predatory['journal']:
            signals.add('predatory_journal', "Journal name appears on a community predatory-journal list")
        if predatory['publisher']:
            signals.add('predatory_publisher', "Publisher appears on a community predatory-publisher list")

        # No Scimago or CORE rank: offer OpenAlex's citation statistics for the venue instead.
        if not result.get('in_sjr') and not result.get('in_core') and openalex.get('source_id'):
            stats = self.fetcher.fetch_openalex_source(openalex['source_id'])
            if stats.get('h_index') is not None or stats.get('mean_citedness_2yr') is not None:
                result['venue_stats'] = stats
                signals.add('venue_stats', "Venue citation statistics taken from OpenAlex (not an official ranking)")

    # ================================================================== deciding the category

    @staticmethod
    def _api_votes(crossref: Dict, openalex: Dict, s2: Dict) -> Dict[str, int]:
        """Score each category using what the metadata services say about the paper."""
        votes = {JOURNAL: 0, CONFERENCE: 0, PREPRINT: 0}

        crossref_type = crossref.get('type', '')
        container = ' '.join(filter(None, [crossref.get('container-title'), crossref.get('event')])).lower()
        if crossref_type == 'journal-article':
            votes[JOURNAL] += 3
        elif crossref_type == 'proceedings-article':
            votes[CONFERENCE] += 3
        elif crossref_type == 'posted-content':
            votes[PREPRINT] += 3
        elif crossref_type in ('book-chapter', 'book-part') and any(w in container for w in CONFERENCE_WORDS):
            # Springer LNCS and similar register conference papers as book chapters.
            votes[CONFERENCE] += 2
        if crossref.get('event'):
            votes[CONFERENCE] += 1

        source_type = openalex.get('source_type')
        work_type = openalex.get('type')
        if source_type == 'journal':
            votes[JOURNAL] += 2
        elif source_type == 'conference' or work_type == 'conference-paper':
            votes[CONFERENCE] += 2
        elif source_type == 'repository' or work_type == 'preprint':
            votes[PREPRINT] += 2

        s2_venue = s2.get('publicationVenue') or {}
        if 'arxiv' not in (s2_venue.get('name') or '').lower():
            if s2_venue.get('type') == 'journal':
                votes[JOURNAL] += 2
            elif s2_venue.get('type') == 'conference':
                votes[CONFERENCE] += 2
        return votes

    def _journal_named_in_text(self, parsed: Dict) -> Optional[Dict]:
        """An SJR journal whose full name is printed in the paper's header or venue line.

        Lines that describe a conference are skipped: 'Language Resources and Evaluation
        Conference' contains the journal 'Language Resources and Evaluation'.
        """
        header = '\n'.join((parsed.get('full_text') or '').split('\n')[:4])
        for text in (parsed.get('venue_context'), parsed.get('venue_context_alt'), header):
            if not text or CONFERENCE_LINE.search(text):
                continue
            journal = self.journal_db.find_in_text(text)
            if journal:
                return journal
        return None

    @staticmethod
    def _text_votes(parsed: Dict, signals: Signals, text_journal: Optional[Dict] = None) -> Dict[str, int]:
        """Score journal vs conference using cues printed in the paper itself."""
        votes = {JOURNAL: 0, CONFERENCE: 0}
        if text_journal:
            votes[JOURNAL] += 2
            signals.add('journal_name_in_text', f"Journal name printed in the paper: {text_journal['title']}")
        if parsed.get('has_review_dates'):
            votes[JOURNAL] += 2
            signals.add('review_dates', "Review dates found (Received/Accepted/Revised)")
        if parsed.get('has_volume_issue') and not parsed.get('has_proceedings'):
            votes[JOURNAL] += 1
            signals.add('volume_issue', "Volume/Issue numbers found")
        if parsed.get('issn'):
            votes[JOURNAL] += 1
            signals.add('issn', f"ISSN found: {parsed['issn']}")
        if parsed.get('has_proceedings'):
            votes[CONFERENCE] += 2
            signals.add('proceedings', "Conference/Proceedings keywords found")
        if parsed.get('has_ieee_conference_footer'):
            votes[CONFERENCE] += 2
            signals.add('ieee_footer', "IEEE conference footer (ISBN/$31.00) detected")
        if parsed.get('isbn'):
            signals.add('isbn', f"ISBN found: {parsed['isbn']}")
            # Books and some journal issues carry ISBNs too, so an ISBN alone decides nothing;
            # it only strengthens other conference evidence.
            if parsed.get('has_proceedings') or parsed.get('has_ieee_conference_footer'):
                votes[CONFERENCE] += 1
        return votes

    @staticmethod
    def _decide(is_arxiv: bool, api_votes: Dict[str, int], text_votes: Dict[str, int],
                weak_arxiv: bool = False) -> str:
        """Pick the category with the strongest evidence.

        weak_arxiv means the arXiv link came from a title search, not from a stamp on the
        PDF: then the PDF may be the published copy, and its own text may decide.
        """
        journal = api_votes[JOURNAL] + text_votes[JOURNAL]
        conference = api_votes[CONFERENCE] + text_votes[CONFERENCE]

        if is_arxiv:
            # An arXiv copy counts as published only if a metadata service names a venue;
            # arXiv PDFs often mention conferences in their text without being published there.
            if max(api_votes[JOURNAL], api_votes[CONFERENCE]) >= 2:
                return JOURNAL if api_votes[JOURNAL] >= api_votes[CONFERENCE] else CONFERENCE
            if weak_arxiv and max(text_votes[JOURNAL], text_votes[CONFERENCE]) >= 2:
                return JOURNAL if text_votes[JOURNAL] >= text_votes[CONFERENCE] else CONFERENCE
            return PREPRINT

        if api_votes[PREPRINT] >= 3 and api_votes[PREPRINT] > max(api_votes[JOURNAL], api_votes[CONFERENCE]):
            return PREPRINT
        if max(journal, conference) >= 2:
            if journal == conference:
                return CONFERENCE if api_votes[CONFERENCE] > api_votes[JOURNAL] else JOURNAL
            return JOURNAL if journal > conference else CONFERENCE
        if max(journal, conference) == 1:
            return JOURNAL if journal >= conference else CONFERENCE
        return 'unknown'

    # ================================================================== building results

    def _base_result(self, parsed: Dict, meta: Dict, category: str) -> Dict[str, Any]:
        """Every result has these keys; the category-specific builders fill in the rest."""
        crossref, openalex, s2 = meta['crossref'], meta['openalex'], meta['s2']
        arxiv = meta.get('arxiv') or {}

        title = (crossref.get('title') or openalex.get('title') or s2.get('title') or
                 arxiv.get('title') or parsed.get('title'))
        s2_authors = ', '.join(a['name'] for a in s2.get('authors') or [] if a.get('name'))
        abstract = s2.get('abstract') or arxiv.get('abstract') or parsed.get('abstract')
        fields = s2.get('fieldsOfStudy') or []
        if not fields and openalex.get('field'):
            fields = [openalex['field']]

        return {
            'title': title or 'Unknown Title',
            'category': category,
            'venue': None,
            'quartile': None,
            'sjr_score': None,
            'h_index': None,
            'journal_id': None,
            'is_arxiv': False,
            'arxiv_id': parsed.get('arxiv_id'),
            'conference_type': None,
            'core_rank': None,
            'core_rank_description': None,
            'suggested_journals': [],
            'confidence': 0.0,
            'signals': [],
            'doi': meta.get('published_doi') or parsed.get('doi') or crossref.get('doi') or openalex.get('doi'),
            'page_count': parsed.get('page_count'),
            'keywords': parsed.get('keywords'),
            'publisher': crossref.get('publisher') or openalex.get('publisher'),
            'categories': None,
            'quartile_color': None,
            'authors': (s2_authors or crossref.get('authors') or openalex.get('authors') or
                        arxiv.get('authors') or parsed.get('authors')),
            'abstract': (abstract[:500] + ('...' if len(abstract) > 500 else '')) if abstract else None,
            'citation_count': s2.get('citationCount') if s2.get('citationCount') is not None else openalex.get('cited_by_count'),
            'year': s2.get('year') or crossref.get('year') or openalex.get('year') or arxiv.get('year'),
            'fields_of_study': ', '.join(fields) if fields else None,
            'topics': openalex.get('topics') or [],
            'is_open_access': openalex.get('is_oa') if openalex.get('is_oa') is not None else s2.get('isOpenAccess'),
            'oa_url': openalex.get('oa_url') or (s2.get('openAccessPdf') or {}).get('url'),
            'is_retracted': bool(openalex.get('is_retracted')),
            'published_doi': meta.get('published_doi'),
            'matched_by': meta.get('matched_by'),
            'openalex_id': openalex.get('id'),
            'in_sjr': None,
            'in_core': None,
            'core_acronym': None,
            'suggestion_field': None,
            'scopus': None,        # Scopus source list entry: active / discontinued / coverage
            'doaj': None,          # DOAJ entry: fees, review process, licence
            'watchlist': None,     # hijacked clone and predatory-list matches
            'venue_stats': None,   # OpenAlex citation statistics when the venue is unranked
            'trust': None,
            'error': None,
        }

    def _classify_journal(self, parsed: Dict, meta: Dict, venue_name: str,
                          signals: Signals, text_journal: Optional[Dict] = None) -> Dict[str, Any]:
        """Classify as journal paper and determine quartile."""
        crossref, openalex, s2 = meta['crossref'], meta['openalex'], meta['s2']
        s2_venue = s2.get('publicationVenue') or {}

        journal_info = None
        issns = self._collect_issns(parsed, meta)
        for issn in issns:
            journal_info = self.journal_db.lookup_by_issn(issn)
            if journal_info:
                signals.add('sjr_issn', f"ISSN match in SJR database: {issn}")
                break

        if not journal_info:
            # A registered ISSN that is not in SJR means the journal is not ranked; a close
            # name match would then point at a different journal, so only exact names count.
            names = [venue_name, openalex.get('source_name'), s2_venue.get('name'),
                     (s2.get('journal') or {}).get('name'), parsed.get('venue')]
            for name in dict.fromkeys(n for n in names if n):
                journal_info = self.journal_db.lookup_by_name(name, fuzzy=not issns)
                if journal_info:
                    signals.add('sjr_name', f"Name match in SJR database: {name}")
                    break

        if not journal_info and text_journal and not issns and not meta['matched_by']:
            # Nothing else identified the journal; the name printed in the header is the best evidence.
            journal_info = text_journal
            signals.add('sjr_name', f"Name match in SJR database: {text_journal['title']}")

        result = self._base_result(parsed, meta, JOURNAL)
        result['venue'] = venue_name or 'Unknown Journal'
        result['quartile'] = 'Unranked'
        if journal_info:
            quartile = journal_info.get('best_quartile') or 'Unranked'
            sjr_score = journal_info.get('sjr_score')
            result.update({
                'venue': journal_info.get('title') or venue_name,
                'quartile': quartile,
                'sjr_score': round(sjr_score, 3) if sjr_score else None,
                'h_index': journal_info.get('h_index'),
                'journal_id': journal_info.get('id'),
                'categories': journal_info.get('categories'),
                'publisher': result['publisher'] or journal_info.get('publisher'),
                'quartile_color': JournalDB.get_quartile_color(quartile),
            })
        result['in_sjr'] = journal_info is not None
        return result

    def _classify_conference(self, parsed: Dict, meta: Dict, venue_name: str,
                             signals: Signals) -> Dict[str, Any]:
        """Classify as conference paper and determine type (IEEE/International/National)."""
        crossref, openalex, s2 = meta['crossref'], meta['openalex'], meta['s2']
        s2_venue = s2.get('publicationVenue') or {}
        names = [crossref.get('event'), venue_name, s2_venue.get('name'), s2.get('venue'),
                 (s2.get('journal') or {}).get('name'), openalex.get('source_name'), parsed.get('venue')]
        names = list(dict.fromkeys(n for n in names if n and 'arxiv' not in n.lower()))

        conference_info = None
        short_names = [a for a in s2_venue.get('alternate_names') or [] if len(a) <= 12]
        contexts = [c for c in (parsed.get('venue_context'), parsed.get('venue_context_alt')) if c]
        for acronym in acronym_candidates(*short_names, *names, *contexts):
            conference_info = self.conference_db.lookup_by_acronym(acronym)
            if conference_info:
                signals.add('core_match', f"CORE database match by acronym: {acronym}")
                break

        if not conference_info:
            for name in names:
                conference_info = self.conference_db.lookup_by_name(clean_venue_name(name))
                if conference_info:
                    signals.add('core_match', "CORE database match by name")
                    break

        if not conference_info:
            for text in (*contexts, *names):
                conference_info = self.conference_db.find_in_text(text or '')
                if conference_info:
                    signals.add('core_match', "CORE database match by name in the venue line")
                    break

        result = self._base_result(parsed, meta, CONFERENCE)
        # "Lecture Notes in Computer Science" is the book series, not the conference.
        venue_is_series = any(w in venue_name.lower() for w in BOOK_SERIES_WORDS)
        # A venue line read from the PDF can carry neighbouring text (two-column layouts);
        # when no metadata service named the venue, the CORE title is the cleaner name.
        api_named_venue = bool(crossref.get('container-title') or crossref.get('event') or
                               openalex.get('source_name') or s2.get('venue'))
        if conference_info and not api_named_venue and conference_info.get('title'):
            venue_name = conference_info['title']
        conference_name = (
            crossref.get('event') or
            (venue_name if venue_name and not venue_is_series else None) or
            (s2.get('venue') if s2.get('venue') and 'arxiv' not in s2['venue'].lower() else None) or
            (conference_info or {}).get('title') or
            venue_name or
            (names[0] if names else None)
        )
        result['venue'] = conference_name or 'Unknown Conference'
        if conference_info:
            rank = conference_info.get('rank') or 'Unranked'
            result['core_rank'] = rank
            result['core_rank_description'] = ConferenceDB.get_rank_description(rank)
            result['core_acronym'] = conference_info.get('acronym')
        result['in_core'] = conference_info is not None
        result['conference_type'] = self._determine_conference_type(parsed, names, result, signals)
        return result

    def _classify_arxiv(self, parsed: Dict, meta: Dict, signals: Signals) -> Dict[str, Any]:
        """Classify as a preprint and suggest suitable journals."""
        openalex, s2 = meta['openalex'], meta['s2']
        signals.add('preprint', "Classified as a preprint (no published venue found)")

        field = self._extract_field(parsed, meta)
        suggested_journals = []
        if field:
            signals.add('field', f"Detected field: {field}")
            suggested_journals = [
                {
                    'id': j.get('id'),
                    'name': j.get('title', ''),
                    'quartile': j.get('best_quartile') or 'Unknown',
                    'sjr_score': round(j.get('sjr_score') or 0, 3),
                    'category': j.get('categories', ''),
                    'publisher': j.get('publisher', ''),
                    'open_access': j.get('open_access') == 'Yes',
                    'quartile_color': JournalDB.get_quartile_color(j.get('best_quartile'))
                }
                for j in self.journal_db.suggest_journals(field, top_n=10)
            ]

        result = self._base_result(parsed, meta, PREPRINT)
        repository = openalex.get('source_name') if openalex.get('source_type') == 'repository' else None
        result['venue'] = repository or 'arXiv'
        result['is_arxiv'] = bool(parsed.get('arxiv_id') or parsed.get('has_arxiv_stamp') or
                                  (s2.get('externalIds') or {}).get('ArXiv'))
        result['arxiv_id'] = parsed.get('arxiv_id') or (s2.get('externalIds') or {}).get('ArXiv')
        result['suggested_journals'] = suggested_journals
        result['suggestion_field'] = field
        return result

    def _determine_conference_type(self, parsed: Dict, names: List[str], result: Dict,
                                   signals: Signals) -> str:
        """Determine if a conference is IEEE, International, or National."""
        text = (parsed.get('full_text') or '')[:3000]
        combined = (text + ' ' + ' '.join(names) + ' ' + (result.get('publisher') or '')).lower()
        doi = (result.get('doi') or '').lower()

        if ('ieee' in ' '.join(names).lower() or 'ieee' in (result.get('publisher') or '').lower() or
                doi.startswith('10.1109/') or parsed.get('has_ieee_conference_footer') or
                re.search(r'\$31\.00\s*©?\s*\d{4}\s*ieee', combined)):
            signals.add('ieee', "IEEE indicators found (copyright, DOI prefix, or keyword)")
            return 'IEEE'

        if ConferenceDB.is_national_rank(result.get('core_rank')):
            signals.add('national', f"CORE lists this as a national/regional event ({result['core_rank']})")
            return 'National'
        for keyword in NATIONAL_KEYWORDS:
            # Word boundaries matter: 'international conference' contains 'national conference'.
            if re.search(r'(?<![a-z])' + re.escape(keyword) + r'\b', combined):
                signals.add('national', f"National conference keyword found: '{keyword}'")
                return 'National'

        signals.add('international', "No IEEE/National indicators → classified as International")
        return 'International'

    def _extract_field(self, parsed: Dict, meta: Dict) -> str:
        """Extract the research field from the paper for journal suggestions."""
        openalex, s2 = meta['openalex'], meta['s2']
        # OpenAlex subfields use the same taxonomy as Scopus, so they match SJR categories.
        for candidate in (openalex.get('subfield'), openalex.get('field')):
            if candidate and self.journal_db.suggest_journals(candidate, top_n=1):
                return candidate

        primary = (meta.get('arxiv') or {}).get('primary_category') or ''
        for prefix, category in ARXIV_TO_SJR_CATEGORY:
            if primary == prefix or primary.startswith((prefix + '.', prefix + '-')):
                return category

        fields_of_study = s2.get('fieldsOfStudy') or []
        if fields_of_study:
            return fields_of_study[0]

        keywords = parsed.get('keywords') or ''
        for keyword in (k.strip() for k in keywords.replace(';', ',').split(',')):
            if keyword and self.journal_db.suggest_journals(keyword, top_n=1):
                return keyword

        text = (parsed.get('full_text') or parsed.get('title') or '').lower()
        field_keywords = {
            'Computer Science': ['algorithm', 'computing', 'software', 'programming'],
            'Artificial Intelligence': ['artificial intelligence', 'reinforcement learning', 'natural language',
                                        'machine learning', 'deep learning', 'neural network'],
            'Computer Vision and Pattern Recognition': ['image processing', 'object detection',
                                                        'computer vision', 'image recognition'],
            'Information Systems': ['data mining', 'big data', 'data analysis', 'analytics'],
            'Computer Networks and Communications': ['security', 'encryption', 'cyber', 'malware', 'intrusion',
                                                     'network', 'wireless', 'iot', 'internet of things', '5g'],
            'Control and Systems Engineering': ['robot', 'autonomous', 'control system', 'sensor'],
            'Medicine': ['clinical', 'patient', 'disease', 'treatment', 'medical'],
            'Engineering': ['engineering', 'structural', 'mechanical', 'thermal'],
            'Physics and Astronomy': ['quantum', 'particle', 'physics', 'thermodynamics'],
            'Mathematics': ['theorem', 'proof', 'mathematical', 'equation'],
            'Biochemistry, Genetics and Molecular Biology': ['gene', 'protein', 'cell', 'biological', 'genome'],
            'Chemistry': ['chemical', 'molecular', 'compound', 'reaction'],
            'Environmental Science': ['climate', 'environmental', 'pollution', 'ecosystem'],
            'Economics, Econometrics and Finance': ['economic', 'market', 'financial', 'trade'],
        }
        best_field, best_count = 'Computer Science', 0
        for field, keywords_list in field_keywords.items():
            count = sum(1 for kw in keywords_list if kw in text)
            if count > best_count:
                best_field, best_count = field, count
        return best_field

    # ================================================================== scoring

    @staticmethod
    def _calculate_confidence(category: str, api_votes: Dict[str, int], text_votes: Dict[str, int],
                              signals: Signals, result: Dict) -> float:
        """How sure we are, from 0.1 to 0.99.

        Agreement between metadata services counts most, the paper's own text counts
        less, and evidence for a different category lowers the score.
        """
        if category == 'unknown':
            return 0.30
        keys = signals.keys

        if category == PREPRINT:
            score = 0.45
            if 'arxiv_id' in keys:
                score += 0.25
            score += min(api_votes[PREPRINT], 3) * 0.06
            if 's2_venue' not in keys and 'crossref_type' not in keys:
                score += 0.05
            score -= min(max(api_votes[JOURNAL], api_votes[CONFERENCE]), 3) * 0.08
        else:
            other = CONFERENCE if category == JOURNAL else JOURNAL
            score = 0.35
            score += min(api_votes[category], 8) * 0.08
            score += min(text_votes.get(category, 0), 4) * 0.03
            score -= min(api_votes[other], 3) * 0.06
            if result.get('in_sjr') or result.get('in_core'):
                score += 0.10
            if 'doi' in keys:
                score += 0.03

        if 'title_mismatch' in keys:
            score -= 0.15
        return round(max(0.10, min(score, 0.99)), 2)

    @staticmethod
    def _trust_check(result: Dict, openalex: Dict) -> Dict[str, Any]:
        """Facts that help a reader judge the venue: indexing, DOAJ, retraction, watchlists."""
        warnings = []
        if result.get('is_retracted'):
            warnings.append('retracted')

        scopus = result.get('scopus') or {}
        in_scopus: Optional[bool] = None
        if result['category'] == JOURNAL:
            in_scopus = bool(scopus) and scopus.get('active', False) and not scopus.get('discontinued')
            if result.get('in_sjr'):
                in_scopus = True
        if scopus.get('discontinued'):
            warnings.append('scopus_discontinued')

        in_doaj = True if result.get('doaj') else openalex.get('is_in_doaj')
        if result['category'] == JOURNAL and not result.get('in_sjr'):
            if in_scopus:
                warnings.append('in_scopus_not_ranked')
            elif in_doaj:
                warnings.append('not_in_sjr_but_in_doaj')
            else:
                warnings.append('not_in_sjr_or_doaj')
        if result['category'] == CONFERENCE and not result.get('in_core'):
            warnings.append('not_in_core')

        watchlist = result.get('watchlist') or {}
        if watchlist.get('hijacked'):
            warnings.append('hijacked_clone_exists')
        if watchlist.get('predatory_journal'):
            warnings.append('name_on_predatory_list')
        if watchlist.get('predatory_publisher'):
            warnings.append('publisher_on_predatory_list')

        return {
            'indexed_in_sjr': result.get('in_sjr') if result['category'] == JOURNAL else None,
            'indexed_in_scopus': in_scopus,
            'in_doaj': in_doaj,
            'in_core': result.get('in_core') if result['category'] == CONFERENCE else None,
            'is_retracted': bool(result.get('is_retracted')),
            'warnings': warnings,
        }

    def _error_result(self, message: str) -> Dict[str, Any]:
        """Return a standardized error result."""
        result = self._base_result(text_metadata.empty_result(),
                                   {'crossref': {}, 'openalex': {}, 's2': {}, 'arxiv': {}}, 'error')
        result.update({'title': 'Error', 'signals': [message], 'error': message, 'page_count': 0})
        return result

    def close(self):
        """Close all database connections."""
        self.journal_db.close()
        self.conference_db.close()
        self.checks.close()
