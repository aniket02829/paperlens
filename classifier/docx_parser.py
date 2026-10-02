"""
Docx parser for extracting text and metadata from research papers.
"""
import re
import logging
from typing import Dict, Any

try:
    import docx
except ImportError:
    docx = None

logger = logging.getLogger(__name__)

class DocxParser:
    """Parses DOCX files to extract text and identify key metadata."""

    def __init__(self):
        # Regular expressions for metadata extraction (same as PDFParser)
        self.doi_pattern = re.compile(r'10\.\d{4,9}/[-._;()/:A-Za-z0-9]+', re.IGNORECASE)
        self.issn_pattern = re.compile(r'(?:ISSN|eISSN|pISSN)?[:\s]*(\d{4}[-\s]?\d{3}[\dX])', re.IGNORECASE)
        self.isbn_pattern = re.compile(r'(?:ISBN(?:-1[03])?:? )?(?=[-0-9 ]{17}$|[-0-9X ]{13}$|[0-9X]{10}$)(?:97[89][- ]?)?[0-9]{1,5}[- ]?(?:[0-9]+[- ]?){2}[0-9X]', re.IGNORECASE)
        self.arxiv_pattern = re.compile(r'arXiv:\s*(\d{4}\.\d{4,5}(?:v\d+)?)', re.IGNORECASE)
        self.arxiv_doi_pattern = re.compile(r'10\.48550/arXiv\.(\d{4}\.\d{4,5}(?:v\d+)?)', re.IGNORECASE)
        self.venue_patterns = [
            re.compile(r'Published in\s*:?\s*(.*)', re.IGNORECASE),
            re.compile(r'Journal of\s+.*', re.IGNORECASE),
            re.compile(r'IEEE Transactions\s+.*', re.IGNORECASE),
            re.compile(r'Proceedings of\s+.*', re.IGNORECASE)
        ]
        self.keywords_pattern = re.compile(r'(?:Keywords|Index Terms)[:\s]*(.*?)(?:\n\n|\n[A-Z]|$)', re.IGNORECASE | re.DOTALL)
        
        # Boolean check patterns
        self.review_dates_pattern = re.compile(r'(Received|Accepted|Revised):', re.IGNORECASE)
        self.vol_issue_pattern = re.compile(r'\b(Vol\.|Volume|Issue|No\.)\b', re.IGNORECASE)
        self.proceedings_pattern = re.compile(r'\b(Proceedings|Conference|Symposium|Workshop)\b', re.IGNORECASE)
        self.ieee_copyright_pattern = re.compile(r'(10\.1109/|\$31\.00|IEEE)', re.IGNORECASE)
        self.arxiv_stamp_pattern = re.compile(r'arXiv:\d{4}\.\d{4,5}', re.IGNORECASE)
        self.abstract_pattern = re.compile(r'(?i)\bAbstract\b[\s\S]*?(?=\b(?:Introduction|Keywords|Index Terms)\b|\n\n\n)', re.IGNORECASE)
        self.email_pattern = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+')

    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a DOCX file and extract text and metadata.
        
        Args:
            file_path: Path to the DOCX file.
            
        Returns:
            Dictionary containing extracted metadata and full text.
        """
        result = {
            'title': None,
            'authors': None,
            'abstract': None,
            'doi': None,
            'issn': None,
            'isbn': None,
            'arxiv_id': None,
            'venue': None,
            'keywords': None,
            'has_review_dates': False,
            'has_volume_issue': False,
            'has_proceedings': False,
            'has_ieee_copyright': False,
            'has_arxiv_stamp': False,
            'full_text': "",
            'page_count': 0  # DOCX doesn't have a clear concept of pages without rendering
        }
        
        if file_path.lower().endswith('.doc'):
            logger.error(f"Unsupported file format: {file_path}. Only .docx files are natively supported.")
            return result
            
        if docx is None:
            logger.error("python-docx is not installed. Please install it using `pip install python-docx`.")
            return result

        try:
            doc = docx.Document(file_path)
            
            # Extract full text
            full_text = []
            for para in doc.paragraphs:
                text = para.text.strip()
                if text:
                    full_text.append(text)
            
            result['full_text'] = '\n'.join(full_text)
            
            # For metadata, consider the first few paragraphs as "front matter"
            front_matter = '\n'.join(full_text[:50])
            if front_matter:
                self._extract_metadata(front_matter, result)
                
                # Extract title
                if full_text:
                    for line in full_text:
                        if len(line) > 5 and not self._is_likely_header_or_logo(line):
                            result['title'] = line
                            break
                            
        except Exception as e:
            logger.error(f"Error parsing DOCX {file_path}: {e}")
            
        return result

    def _extract_metadata(self, text: str, result: Dict[str, Any]) -> None:
        """Extract metadata from text using regex patterns."""
        # DOI
        doi_match = self.doi_pattern.search(text)
        if doi_match:
            result['doi'] = doi_match.group(0).rstrip('.')
            
        # ISSN
        issn_match = self.issn_pattern.search(text)
        if issn_match:
            result['issn'] = issn_match.group(1)
            
        # ISBN
        isbn_match = self.isbn_pattern.search(text)
        if isbn_match:
            result['isbn'] = isbn_match.group(0)
            
        # ArXiv ID
        arxiv_match = self.arxiv_pattern.search(text)
        if arxiv_match:
            result['arxiv_id'] = arxiv_match.group(1)
        else:
            arxiv_doi_match = self.arxiv_doi_pattern.search(text)
            if arxiv_doi_match:
                result['arxiv_id'] = arxiv_doi_match.group(1)
                
        # Venue
        for pattern in self.venue_patterns:
            venue_match = pattern.search(text)
            if venue_match:
                result['venue'] = venue_match.group(1) if venue_match.groups() else venue_match.group(0)
                break
                
        # Keywords
        keywords_match = self.keywords_pattern.search(text)
        if keywords_match:
            result['keywords'] = ' '.join(keywords_match.group(1).split())
            
        # Booleans
        result['has_review_dates'] = bool(self.review_dates_pattern.search(text))
        result['has_volume_issue'] = bool(self.vol_issue_pattern.search(text))
        result['has_proceedings'] = bool(self.proceedings_pattern.search(text))
        result['has_ieee_copyright'] = bool(self.ieee_copyright_pattern.search(text))
        result['has_arxiv_stamp'] = bool(self.arxiv_stamp_pattern.search(text))
        
        # Abstract
        abstract_match = self.abstract_pattern.search(text)
        if abstract_match:
            abs_text = abstract_match.group(0)
            # Remove the 'Abstract' heading
            abs_text = re.sub(r'^(?i)\bAbstract\b[\s\.:\-]*', '', abs_text).strip()
            result['abstract'] = abs_text
            
        # Authors heuristic
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        title_idx = -1
        for i, line in enumerate(lines[:20]):
            if len(line) > 5 and not self._is_likely_header_or_logo(line):
                title_idx = i
                break
                
        if title_idx != -1 and title_idx + 1 < len(lines):
            # Look at next few lines for authors
            author_lines = []
            for line in lines[title_idx + 1:title_idx + 6]:
                if line.lower().startswith('abstract'):
                    break
                # If there's an email or generic university/dept wording, it might be affiliation
                if self.email_pattern.search(line) or any(w in line.lower() for w in ['university', 'institute', 'department', 'school']):
                    # Skip or keep as affiliation? We just want authors
                    pass
                else:
                    # Very simple heuristic: names are separated by commas or 'and'
                    if ',' in line or ' and ' in line.lower() or len(line.split()) <= 6:
                        author_lines.append(line)
            
            if author_lines:
                result['authors'] = ' '.join(author_lines)

    def _is_likely_header_or_logo(self, text: str) -> bool:
        """Heuristic check to skip headers or logos for title extraction."""
        text_lower = text.lower()
        if 'arxiv' in text_lower or 'doi' in text_lower or 'issn' in text_lower:
            return True
        if text_lower.startswith('published in') or text_lower.startswith('vol.') or text_lower.startswith('volume'):
            return True
        return False
