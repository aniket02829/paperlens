"""
Metadata extraction shared by the PDF and DOCX parsers.

Both parsers turn a document into plain text, then call extract_metadata() on the
front matter (the first pages) so they detect DOIs, ISSNs and venue cues the same way.
"""
import re
from typing import Any, Dict, List, Optional

DOI_PATTERN = re.compile(r'\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+', re.IGNORECASE)
BROKEN_DOI_PATTERN = re.compile(r'(\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]*[./\-_])\n([A-Za-z0-9])')
LABELED_ISSN_PATTERN = re.compile(r'\b[ep]?-?ISSN\b[^0-9]{0,20}(\d{4}\s?-?\s?\d{3}[\dXx])', re.IGNORECASE)
BARE_ISSN_PATTERN = re.compile(r'\b(\d{4}-\d{3}[\dXx])\b')
ISBN_PATTERN = re.compile(r'\bISBN(?:-1[03])?\s*:?\s*((?:97[89][-\s]?)?\d{1,5}[-\s]?\d{1,7}[-\s]?\d{1,7}[-\s]?[\dXx])\b', re.IGNORECASE)
ARXIV_PATTERN = re.compile(r'arXiv\s*:\s*(\d{4}\.\d{4,5}(?:v\d+)?|[a-z\-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)', re.IGNORECASE)
ARXIV_DOI_PATTERN = re.compile(r'10\.48550/arXiv\.(\d{4}\.\d{4,5}(?:v\d+)?)', re.IGNORECASE)
VENUE_PATTERNS = [
    re.compile(r'Published in\s*:?\s*(.*)', re.IGNORECASE),
    re.compile(r'Journal of\s+.*', re.IGNORECASE),
    re.compile(r'IEEE Transactions\s+.*', re.IGNORECASE),
    re.compile(r'Proceedings of\s+.*', re.IGNORECASE)
]
KEYWORDS_PATTERN = re.compile(r'(?:Keywords|Index Terms)[:\s—-]*(.*?)(?:\n\n|\n[A-Z]|$)', re.IGNORECASE | re.DOTALL)
REVIEW_DATES_PATTERN = re.compile(r'(Received|Accepted|Revised)\s*:?\s*\d{1,2}\s+[A-Za-z]+\s+\d{4}|(Received|Accepted|Revised):', re.IGNORECASE)
VOL_ISSUE_PATTERN = re.compile(r'\b(Vol\.|Volume|Issue|No\.)\s*\d+', re.IGNORECASE)
PROCEEDINGS_PATTERN = re.compile(r'\b(Proceedings|Conference|Symposium|Workshop)\b', re.IGNORECASE)
IEEE_COPYRIGHT_PATTERN = re.compile(r'(10\.1109/|©\s*\d{4}\s*IEEE|\(c\)\s*\d{4}\s*IEEE|\$31\.00|\bIEEE\b)', re.IGNORECASE)
# The footer printed on IEEE conference papers, e.g. "978-1-6654-4509-2/22/$31.00 ©2022 IEEE".
IEEE_CONFERENCE_FOOTER_PATTERN = re.compile(r'97[89][-\d]{10,16}/\d{2}/\$\d+\.\d{2}')
ARXIV_STAMP_PATTERN = re.compile(r'arXiv:\d{4}\.\d{4,5}', re.IGNORECASE)
ABSTRACT_PATTERN = re.compile(r'\bAbstract\b[\s\S]*?(?=\b(?:Introduction|Keywords|Index Terms)\b|\n\n\n)', re.IGNORECASE)
EMAIL_PATTERN = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')
YEAR_RANGE_PATTERN = re.compile(r'^(19|20)\d{2}-?(19|20)\d{1}[\dX]$')


def empty_result() -> Dict[str, Any]:
    """The dict shape every parser returns."""
    return {
        'title': None,
        'authors': None,
        'abstract': None,
        'doi': None,
        'issn': None,
        'isbn': None,
        'arxiv_id': None,
        'venue': None,
        'venue_context': None,
        'venue_context_alt': None,   # the venue line read column by column (two-column layouts)
        'looks_scanned': False,
        'keywords': None,
        'has_review_dates': False,
        'has_volume_issue': False,
        'has_proceedings': False,
        'has_ieee_copyright': False,
        'has_ieee_conference_footer': False,
        'has_arxiv_stamp': False,
        'full_text': "",
        'page_count': 0
    }


def clean_doi(doi: str) -> str:
    """Strip the trailing punctuation that regexes pick up from surrounding text."""
    doi = doi.strip().rstrip('.,;:')
    # A closing parenthesis is part of the DOI only if it has a matching opening one.
    while doi.endswith(')') and doi.count('(') < doi.count(')'):
        doi = doi[:-1].rstrip('.,;:')
    return doi


def is_valid_issn(issn: str) -> bool:
    """Check an ISSN against its check digit (the 8th character)."""
    digits = issn.replace('-', '').replace(' ', '').upper()
    if len(digits) != 8 or not digits[:7].isdigit():
        return False
    total = sum(int(d) * w for d, w in zip(digits[:7], range(8, 1, -1)))
    check = (11 - total % 11) % 11
    expected = 'X' if check == 10 else str(check)
    return digits[7] == expected


def format_issn(issn: str) -> str:
    digits = issn.replace('-', '').replace(' ', '').upper()
    return f'{digits[:4]}-{digits[4:]}'


def find_issn(text: str) -> Optional[str]:
    """Return the first valid ISSN, preferring ones labeled 'ISSN' in the text."""
    for match in LABELED_ISSN_PATTERN.finditer(text):
        if is_valid_issn(match.group(1)):
            return format_issn(match.group(1))
    for match in BARE_ISSN_PATTERN.finditer(text):
        candidate = match.group(1)
        # "2019-2020" looks like an ISSN; skip year ranges even if the checksum passes.
        if is_valid_issn(candidate) and not YEAR_RANGE_PATTERN.match(candidate):
            return format_issn(candidate)
    return None


def is_likely_header_or_logo(text: str) -> bool:
    """Heuristic check to skip headers or logos for title extraction."""
    text_lower = text.lower()
    if 'arxiv' in text_lower or 'doi' in text_lower or 'issn' in text_lower:
        return True
    if text_lower.startswith('published in') or text_lower.startswith('vol.') or text_lower.startswith('volume'):
        return True
    if EMAIL_PATTERN.search(text) or text_lower.startswith('http'):
        return True
    return False


def first_plausible_line(lines: List[str]) -> Optional[str]:
    for line in lines:
        if len(line) > 5 and not is_likely_header_or_logo(line):
            return line
    return None


def join_broken_dois(text: str) -> str:
    """Rejoin DOIs that wrap onto the next line: '10.1371/journal.\\npgph.0000583'."""
    return BROKEN_DOI_PATTERN.sub(r'\1\2', text)


def find_venue(text: str):
    """Return (venue, venue_context) for the first venue line in text, or (None, None).

    venue_context is the venue line plus the next line: venue lines often wrap
    ("...Conference on Machine\\nLearning"), and words hyphenated across the break
    are rejoined.
    """
    for pattern in VENUE_PATTERNS:
        venue_match = pattern.search(text)
        if venue_match:
            venue = venue_match.group(1) if venue_match.groups() else venue_match.group(0)
            # The whole line, not just from the match: '© Canadian Journal of Sociology' must
            # keep 'Canadian'.
            line_start = text.rfind('\n', 0, venue_match.start()) + 1
            line = text[line_start:venue_match.end()].strip()
            rest = text[venue_match.end():].lstrip('\n').split('\n', 1)[0]
            joined = line[:-1] + rest if line.endswith('-') else f'{line} {rest}'
            return venue.strip()[:200], joined.strip()[:300]
    return None, None


def extract_metadata(text: str, result: Dict[str, Any], first_page_text: Optional[str] = None) -> None:
    """Fill result with identifiers and venue cues found in the front matter text."""
    doi_match = DOI_PATTERN.search(join_broken_dois(text))
    if doi_match:
        result['doi'] = clean_doi(doi_match.group(0))

    result['issn'] = find_issn(text)

    isbn_match = ISBN_PATTERN.search(text)
    if isbn_match:
        result['isbn'] = isbn_match.group(1)

    arxiv_match = ARXIV_PATTERN.search(text)
    if arxiv_match:
        result['arxiv_id'] = arxiv_match.group(1)
    else:
        arxiv_doi_match = ARXIV_DOI_PATTERN.search(text)
        if arxiv_doi_match:
            result['arxiv_id'] = arxiv_doi_match.group(1)

    result['venue'], result['venue_context'] = find_venue(text)

    keywords_match = KEYWORDS_PATTERN.search(text)
    if keywords_match:
        result['keywords'] = ' '.join(keywords_match.group(1).split())[:500]

    result['has_review_dates'] = bool(REVIEW_DATES_PATTERN.search(text))
    result['has_volume_issue'] = bool(VOL_ISSUE_PATTERN.search(text))
    result['has_proceedings'] = bool(PROCEEDINGS_PATTERN.search(text))
    result['has_ieee_copyright'] = bool(IEEE_COPYRIGHT_PATTERN.search(text))
    result['has_ieee_conference_footer'] = bool(IEEE_CONFERENCE_FOOTER_PATTERN.search(text))
    result['has_arxiv_stamp'] = bool(ARXIV_STAMP_PATTERN.search(first_page_text if first_page_text is not None else text))

    abstract_match = ABSTRACT_PATTERN.search(text)
    if abstract_match:
        abs_text = re.sub(r'^\bAbstract\b[\s\.:\-—]*', '', abstract_match.group(0), flags=re.IGNORECASE).strip()
        result['abstract'] = abs_text or None

    result['authors'] = guess_authors(text)


def guess_authors(text: str) -> Optional[str]:
    """Take the short lines right after the title as the author list."""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    title_idx = -1
    for i, line in enumerate(lines[:20]):
        if len(line) > 5 and not is_likely_header_or_logo(line):
            title_idx = i
            break
    if title_idx == -1:
        return None

    author_lines = []
    for line in lines[title_idx + 1:title_idx + 6]:
        if line.lower().startswith('abstract'):
            break
        # Skip affiliation lines (emails, universities, departments)
        if EMAIL_PATTERN.search(line) or any(w in line.lower() for w in ['university', 'institute', 'department', 'school']):
            continue
        if ',' in line or ' and ' in line.lower() or len(line.split()) <= 6:
            author_lines.append(line)
    return ' '.join(author_lines) if author_lines else None
