"""
PDF parser for extracting text and metadata from research papers.
"""
import logging
from typing import Dict, Any, List, Optional

from classifier import text_metadata

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

logger = logging.getLogger(__name__)

# pdfplumber's default (3) merges tightly set words: "ProceedingsofMachineLearning".
X_TOLERANCE = 1.5

# Fewer characters per page than this, on pages that carry images, means the text is
# in the images (a scanned paper) and only stray footnotes or page numbers were read.
SCANNED_CHARS_PER_PAGE = 300

# Document-info titles that word processors fill in automatically and that are not real titles
BAD_METADATA_TITLE_PREFIXES = ('microsoft word', 'untitled', 'title', 'paper', 'manuscript', 'doi:')


class PDFParser:
    """Parses PDF files to extract text and identify key metadata."""

    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a PDF file and extract text and metadata.

        Args:
            file_path: Path to the PDF file.

        Returns:
            Dictionary containing extracted metadata and full text.
        """
        result = text_metadata.empty_result()

        if pdfplumber is None:
            logger.error("pdfplumber is not installed. Please install it to parse PDFs.")
            return result

        try:
            with pdfplumber.open(file_path) as pdf:
                result['page_count'] = len(pdf.pages)

                page_texts = [page.extract_text(x_tolerance=X_TOLERANCE) or '' for page in pdf.pages]
                if page_texts:
                    # The arXiv stamp runs sideways up the margin, and extract_text skips rotated text.
                    sideways = self._rotated_text(pdf.pages[0])
                    if sideways:
                        page_texts[0] = sideways + '\n' + page_texts[0]
                result['full_text'] = '\n'.join(t for t in page_texts if t)
                result['looks_scanned'] = self._looks_scanned(pdf.pages, page_texts)

                front_pages_text = '\n'.join(page_texts[:2])
                if front_pages_text.strip():
                    text_metadata.extract_metadata(front_pages_text, result, first_page_text=page_texts[0])

                    # In two-column papers extract_text interleaves the columns, which cuts
                    # a venue footnote in half; read the front pages column by column too.
                    columns_text = '\n'.join(self._column_text(page) for page in pdf.pages[:2])
                    _, alt_context = text_metadata.find_venue(columns_text)
                    if alt_context and alt_context != result['venue_context']:
                        result['venue_context_alt'] = alt_context

                    lines = [line.strip() for line in front_pages_text.split('\n') if line.strip()]
                    result['title'] = (
                        self._title_from_font_size(pdf.pages[0]) or
                        self._title_from_document_info(pdf.metadata) or
                        text_metadata.first_plausible_line(lines)
                    )

        except Exception as e:
            logger.error(f"Error parsing PDF {file_path}: {e}")

        return result

    @staticmethod
    def _looks_scanned(pages, page_texts: List[str]) -> bool:
        """True when the front pages are pictures with little or no extractable text.

        Only the first two pages matter: that is where the title, DOI and venue are,
        and some scanned papers carry typed footnotes or references further on.
        """
        front = list(zip(pages[:2], page_texts[:2]))
        if not front:
            return False
        for page, text in front:
            if len(text) >= SCANNED_CHARS_PER_PAGE:
                return False
            try:
                if not page.images:
                    return False
            except Exception:
                return False
        return True

    @staticmethod
    def _column_text(page) -> str:
        """The page text read as two columns (left half, then right half)."""
        try:
            half = page.width / 2
            left = page.crop((0, 0, half, page.height)).extract_text(x_tolerance=X_TOLERANCE) or ''
            right = page.crop((half, 0, page.width, page.height)).extract_text(x_tolerance=X_TOLERANCE) or ''
        except Exception:
            return ''
        return f'{left}\n{right}'

    @staticmethod
    def _rotated_text(page) -> str:
        """Join the characters on a page that are not upright (e.g. the arXiv margin stamp)."""
        # The PDF's own drawing order already reads correctly, so keep it.
        return ''.join(c['text'] for c in page.chars if not c.get('upright', True))

    @staticmethod
    def _lines(words, tolerance: float = 4.0) -> List[List[Dict]]:
        """Group words into lines by their baseline, each line sorted left to right."""
        lines: List[List[Dict]] = []
        for word in sorted(words, key=lambda w: (round(w['bottom']), w['x0'])):
            if lines and abs(lines[-1][-1]['bottom'] - word['bottom']) <= tolerance:
                lines[-1].append(word)
            else:
                lines.append([word])
        return [sorted(line, key=lambda w: w['x0']) for line in lines]

    @staticmethod
    def _join_line(line: List[Dict]) -> str:
        """Join a line's words, closing the gap after decorative initials ('S' + 'hould')."""
        text = ''
        for previous, word in zip([None] + line[:-1], line):
            if previous is not None:
                text += '' if word['x0'] - previous['x1'] < 1.0 else ' '
            text += word['text']
        return text

    @classmethod
    def _title_from_font_size(cls, page) -> Optional[str]:
        """Return the largest text in the top half of the first page, which is usually the title.

        Whole lines are taken, not just the big words: titles set in small capitals
        print the initials larger than the rest of each word.
        """
        try:
            words = page.extract_words(extra_attrs=['size'], keep_blank_chars=False)
        except Exception:
            return None
        top_half = [w for w in words if w['top'] < page.height / 2]
        if not top_half:
            return None
        lines = cls._lines(top_half)
        sizes = sorted({round(w['size'], 1) for w in top_half}, reverse=True)
        for size in sizes[:3]:
            title_lines = [line for line in lines if any(round(w['size'], 1) == size for w in line)]
            # Keep the words that belong to the same heading: not footnote-sized text on the line.
            title_lines = [[w for w in line if w['size'] >= size * 0.6] for line in title_lines]
            title = ' '.join(cls._join_line(line) for line in title_lines if line)
            tokens = title.split()
            # Skip journal banners, lone big letters and author superscripts; a real title has
            # several words, most of them longer than one character.
            if 3 <= len(tokens) <= 40 and sum(len(t) > 1 for t in tokens) >= 3 \
                    and not text_metadata.is_likely_header_or_logo(title):
                return title
        return None

    @staticmethod
    def _title_from_document_info(metadata: Dict) -> Optional[str]:
        title = (metadata or {}).get('Title')
        if not isinstance(title, str):
            return None
        title = title.strip()
        if len(title.split()) < 3 or title.lower().startswith(BAD_METADATA_TITLE_PREFIXES):
            return None
        if title.lower().endswith(('.pdf', '.doc', '.docx', '.dvi', '.tex')):
            return None
        return title
