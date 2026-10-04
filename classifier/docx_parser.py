"""
Docx parser for extracting text and metadata from research papers.
"""
import logging
from typing import Dict, Any

from classifier import text_metadata

try:
    import docx
except ImportError:
    docx = None

logger = logging.getLogger(__name__)


class DocxParser:
    """Parses DOCX files to extract text and identify key metadata."""

    def parse(self, file_path: str) -> Dict[str, Any]:
        """
        Parse a DOCX file and extract text and metadata.

        Args:
            file_path: Path to the DOCX file.

        Returns:
            Dictionary containing extracted metadata and full text.
            page_count stays 0 because DOCX has no pages until it is rendered.
        """
        result = text_metadata.empty_result()

        if docx is None:
            logger.error("python-docx is not installed. Please install it using `pip install python-docx`.")
            return result

        try:
            doc = docx.Document(file_path)

            paragraphs = [para.text.strip() for para in doc.paragraphs if para.text.strip()]
            result['full_text'] = '\n'.join(paragraphs)

            # Treat the first paragraphs as the front matter
            front_matter = '\n'.join(paragraphs[:50])
            if front_matter:
                text_metadata.extract_metadata(front_matter, result)
                core_title = (doc.core_properties.title or '').strip()
                result['title'] = (
                    core_title if len(core_title.split()) >= 3 else
                    text_metadata.first_plausible_line(paragraphs)
                )

        except Exception as e:
            logger.error(f"Error parsing DOCX {file_path}: {e}")

        return result
