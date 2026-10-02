"""
Core classifier engine for research paper classification.

This module ties together the PDF/DOCX parsers, metadata fetcher, journal DB,
and conference DB to produce a final classification for any uploaded paper.
"""
import re
import logging
from typing import Dict, Any, List, Optional

from classifier.pdf_parser import PDFParser
from classifier.docx_parser import DocxParser
from classifier.metadata_fetcher import MetadataFetcher
from classifier.journal_db import JournalDB
from classifier.conference_db import ConferenceDB

logger = logging.getLogger(__name__)


class PaperClassifier:
    """
    Main classification engine that analyzes a research paper and determines:
    - Whether it's a Journal paper, Conference paper, or Arxiv preprint
    - If Journal: which quartile (Q1-Q4), SJR score, journal name
    - If Conference: whether it's IEEE, International, or National + CORE rank
    - If Arxiv: suggests suitable journals for publication
    """

    def __init__(self, db_path: str, crossref_email: str,
                 semantic_scholar_api_key: Optional[str] = None):
        """
        Initialize the classifier with all required components.

        Args:
            db_path: Path to the SQLite database containing journal/conference data.
            crossref_email: Email for CrossRef polite pool.
            semantic_scholar_api_key: Optional Semantic Scholar API key.
        """
        self.pdf_parser = PDFParser()
        self.docx_parser = DocxParser()
        self.fetcher = MetadataFetcher(crossref_email, semantic_scholar_api_key)
        self.journal_db = JournalDB(db_path)
        self.conference_db = ConferenceDB(db_path)

    def classify(self, file_path: str) -> Dict[str, Any]:
        """
        Classify a research paper from its file path.

        Args:
            file_path: Path to the uploaded PDF or DOCX file.

        Returns:
            Dictionary containing the full classification result.
        """
        # Step 0: Parse the document
        if file_path.lower().endswith('.pdf'):
            parsed = self.pdf_parser.parse(file_path)
        elif file_path.lower().endswith('.docx'):
            parsed = self.docx_parser.parse(file_path)
        else:
            return self._error_result("Unsupported file format. Please upload a PDF or DOCX file.")

        if not parsed.get('full_text'):
            return self._error_result("Could not extract text from the document. The file may be corrupt or scanned.")

        signals = []
        confidence = 0.0

        # Step 1: Check for Arxiv preprint
        is_arxiv = False
        arxiv_id = parsed.get('arxiv_id')
        if arxiv_id or parsed.get('has_arxiv_stamp'):
            is_arxiv = True
            signals.append(f"Arxiv ID detected: {arxiv_id or 'stamp found'}")

        # Step 2: Try to enrich via DOI using CrossRef
        crossref_data = {}
        doi = parsed.get('doi')
        if doi:
            signals.append(f"DOI found: {doi}")
            crossref_data = self.fetcher.fetch_by_doi(doi)
            if crossref_data:
                signals.append(f"CrossRef type: {crossref_data.get('type', 'unknown')}")
        elif parsed.get('title'):
            # Fallback: search by title
            crossref_data = self.fetcher.fetch_by_title(parsed['title'])
            if crossref_data:
                signals.append(f"CrossRef title match, type: {crossref_data.get('type', 'unknown')}")

        # Step 3: Try Semantic Scholar for additional context
        s2_data = {}
        if doi:
            s2_data = self.fetcher.fetch_semantic_scholar(doi)
        elif arxiv_id:
            s2_data = self.fetcher.fetch_semantic_scholar(f"arXiv:{arxiv_id}")

        if s2_data:
            s2_venue = s2_data.get('venue', '')
            if s2_venue:
                signals.append(f"Semantic Scholar venue: {s2_venue}")
            pub_venue = s2_data.get('publicationVenue') or {}
            if pub_venue.get('type'):
                signals.append(f"S2 venue type: {pub_venue['type']}")

        # Step 4: Determine category
        crossref_type = crossref_data.get('type', '')
        s2_venue_type = (s2_data.get('publicationVenue') or {}).get('type', '')

        # Determine the venue name from multiple sources
        venue_name = (
            crossref_data.get('container-title') or
            s2_data.get('venue') or
            parsed.get('venue') or
            ''
        )

        # ----- ARXIV PREPRINT -----
        if is_arxiv and not crossref_type:
            result = self._classify_arxiv(parsed, venue_name, signals, s2_data)

        # ----- JOURNAL ARTICLE -----
        elif self._is_journal(crossref_type, s2_venue_type, parsed, signals):
            result = self._classify_journal(parsed, crossref_data, venue_name, signals, s2_data)

        # ----- CONFERENCE PAPER -----
        elif self._is_conference(crossref_type, s2_venue_type, parsed, signals):
            result = self._classify_conference(parsed, crossref_data, venue_name, signals, s2_data)

        # ----- ARXIV WITH PUBLISHED VENUE -----
        elif is_arxiv:
            # Has arxiv stamp but also has a published venue (dual publication)
            if crossref_type == 'journal-article':
                result = self._classify_journal(parsed, crossref_data, venue_name, signals, s2_data)
                result['is_arxiv'] = True
                result['arxiv_id'] = arxiv_id
                signals.append("Paper is also available on Arxiv")
            elif crossref_type == 'proceedings-article':
                result = self._classify_conference(parsed, crossref_data, venue_name, signals, s2_data)
                result['is_arxiv'] = True
                result['arxiv_id'] = arxiv_id
                signals.append("Paper is also available on Arxiv")
            else:
                result = self._classify_arxiv(parsed, venue_name, signals, s2_data)

        # ----- HEURISTIC FALLBACK -----
        else:
            result = self._heuristic_fallback(parsed, venue_name, signals)
            
        # ----- ENRICH WITH NEW FIELDS -----
        s2_authors = s2_data.get('authors', []) if s2_data else []
        if s2_authors:
            result['authors'] = ', '.join([a.get('name', '') for a in s2_authors if a.get('name')])
        else:
            result['authors'] = parsed.get('authors')
            
        abstract = (s2_data.get('abstract') if s2_data else None) or parsed.get('abstract')
        if abstract:
            result['abstract'] = abstract[:500] + ('...' if len(abstract) > 500 else '')
        else:
            result['abstract'] = None
            
        result['citation_count'] = s2_data.get('citationCount') if s2_data else None
        
        year = s2_data.get('year') if s2_data else None
        if not year and crossref_data:
            year = crossref_data.get('year')
        result['year'] = year
        
        fields = s2_data.get('fieldsOfStudy', []) if s2_data else []
        result['fields_of_study'] = ', '.join(fields) if fields else None
        
        return result

    def _is_journal(self, crossref_type: str, s2_venue_type: str,
                    parsed: Dict, signals: List[str]) -> bool:
        """Determine if the paper is likely a journal article."""
        score = 0

        if crossref_type == 'journal-article':
            score += 3
        if s2_venue_type == 'journal':
            score += 2
        if parsed.get('has_review_dates'):
            score += 2
            signals.append("Review dates found (Received/Accepted/Revised)")
        if parsed.get('has_volume_issue') and not parsed.get('has_proceedings'):
            score += 1
            signals.append("Volume/Issue numbers found")
        if parsed.get('issn'):
            score += 1
            signals.append(f"ISSN found: {parsed['issn']}")

        return score >= 2

    def _is_conference(self, crossref_type: str, s2_venue_type: str,
                       parsed: Dict, signals: List[str]) -> bool:
        """Determine if the paper is likely a conference paper."""
        score = 0

        if crossref_type == 'proceedings-article':
            score += 3
        if s2_venue_type == 'conference':
            score += 2
        if parsed.get('has_proceedings'):
            score += 2
            signals.append("Conference/Proceedings keywords found")
        if parsed.get('has_ieee_copyright'):
            score += 1
            signals.append("IEEE copyright/identifier detected")
        if parsed.get('isbn'):
            score += 1
            signals.append(f"ISBN found: {parsed['isbn']}")

        return score >= 2

    def _classify_journal(self, parsed: Dict, crossref_data: Dict,
                          venue_name: str, signals: List[str],
                          s2_data: Dict) -> Dict[str, Any]:
        """Classify as journal paper and determine quartile."""
        quartile = None
        sjr_score = None
        journal_info = None

        # Try lookup by ISSN first (most reliable)
        issns = crossref_data.get('issn', [])
        if parsed.get('issn'):
            issns.append(parsed['issn'])

        for issn in issns:
            journal_info = self.journal_db.lookup_by_issn(issn)
            if journal_info:
                signals.append(f"ISSN match in SJR database: {issn}")
                break

        # Fallback: lookup by name
        if not journal_info and venue_name:
            journal_info = self.journal_db.lookup_by_name(venue_name)
            if journal_info:
                signals.append(f"Name match in SJR database: {venue_name}")

        if journal_info:
            quartile = journal_info.get('best_quartile', 'Unknown')
            sjr_score = journal_info.get('sjr_score')
            venue_name = journal_info.get('title', venue_name)

        # Calculate confidence
        confidence = self._calculate_confidence(signals, 'journal')

        return {
            'title': parsed.get('title', 'Unknown Title'),
            'category': 'journal',
            'venue': venue_name or 'Unknown Journal',
            'quartile': quartile or 'Unranked',
            'sjr_score': round(sjr_score, 3) if sjr_score else None,
            'is_arxiv': False,
            'arxiv_id': parsed.get('arxiv_id'),
            'conference_type': None,
            'core_rank': None,
            'suggested_journals': [],
            'confidence': confidence,
            'signals': signals,
            'doi': parsed.get('doi'),
            'page_count': parsed.get('page_count', 0),
            'keywords': parsed.get('keywords'),
            'publisher': crossref_data.get('publisher') or (journal_info or {}).get('publisher'),
            'categories': (journal_info or {}).get('categories'),
            'quartile_color': JournalDB.get_quartile_color(quartile)
        }

    def _classify_conference(self, parsed: Dict, crossref_data: Dict,
                             venue_name: str, signals: List[str],
                             s2_data: Dict) -> Dict[str, Any]:
        """Classify as conference paper and determine type (IEEE/International/National)."""
        conference_type = self._determine_conference_type(parsed, venue_name, signals)
        core_rank = None
        core_rank_desc = None
        conference_info = None

        # Try to find in CORE database
        # Extract acronym from venue name
        acronyms = re.findall(r'\b([A-Z]{2,}[0-9]*)\b', venue_name)
        for acronym in acronyms:
            conference_info = self.conference_db.lookup_by_acronym(acronym)
            if conference_info:
                signals.append(f"CORE database match by acronym: {acronym}")
                break

        if not conference_info and venue_name:
            conference_info = self.conference_db.lookup_by_name(venue_name)
            if conference_info:
                signals.append(f"CORE database match by name")

        if conference_info:
            core_rank = conference_info.get('rank', 'Unranked')
            core_rank_desc = ConferenceDB.get_rank_description(core_rank)
            if not venue_name:
                venue_name = conference_info.get('title', venue_name)

        confidence = self._calculate_confidence(signals, 'conference')

        return {
            'title': parsed.get('title', 'Unknown Title'),
            'category': 'conference',
            'venue': venue_name or 'Unknown Conference',
            'quartile': None,
            'sjr_score': None,
            'is_arxiv': False,
            'arxiv_id': parsed.get('arxiv_id'),
            'conference_type': conference_type,
            'core_rank': core_rank,
            'core_rank_description': core_rank_desc,
            'suggested_journals': [],
            'confidence': confidence,
            'signals': signals,
            'doi': parsed.get('doi'),
            'page_count': parsed.get('page_count', 0),
            'keywords': parsed.get('keywords'),
            'publisher': crossref_data.get('publisher'),
            'categories': None,
            'quartile_color': None
        }

    def _classify_arxiv(self, parsed: Dict, venue_name: str,
                        signals: List[str], s2_data: Dict) -> Dict[str, Any]:
        """Classify as Arxiv preprint and suggest suitable journals."""
        signals.append("Classified as Arxiv preprint (no published venue found)")

        # Determine field for journal suggestions
        field = self._extract_field(parsed, s2_data)
        suggested_journals = []

        if field:
            signals.append(f"Detected field: {field}")
            raw_suggestions = self.journal_db.suggest_journals(field, top_n=10)
            suggested_journals = [
                {
                    'name': j.get('title', ''),
                    'quartile': j.get('best_quartile', 'Unknown'),
                    'sjr_score': round(j.get('sjr_score', 0), 3),
                    'category': j.get('categories', ''),
                    'publisher': j.get('publisher', ''),
                    'quartile_color': JournalDB.get_quartile_color(j.get('best_quartile'))
                }
                for j in raw_suggestions
            ]

        confidence = self._calculate_confidence(signals, 'arxiv')

        return {
            'title': parsed.get('title', 'Unknown Title'),
            'category': 'arxiv',
            'venue': 'Arxiv Preprint',
            'quartile': None,
            'sjr_score': None,
            'is_arxiv': True,
            'arxiv_id': parsed.get('arxiv_id'),
            'conference_type': None,
            'core_rank': None,
            'suggested_journals': suggested_journals,
            'confidence': confidence,
            'signals': signals,
            'doi': parsed.get('doi'),
            'page_count': parsed.get('page_count', 0),
            'keywords': parsed.get('keywords'),
            'publisher': None,
            'categories': None,
            'quartile_color': None
        }

    def _heuristic_fallback(self, parsed: Dict, venue_name: str,
                            signals: List[str]) -> Dict[str, Any]:
        """Fallback classification using text heuristics when APIs don't help."""
        signals.append("Using heuristic fallback (no API match found)")

        text = (parsed.get('full_text', '') + ' ' + venue_name).lower()

        # Check for strong journal signals
        has_review = parsed.get('has_review_dates', False)
        has_vol = parsed.get('has_volume_issue', False)
        has_proc = parsed.get('has_proceedings', False)
        has_ieee = parsed.get('has_ieee_copyright', False)

        if has_review or (has_vol and not has_proc):
            signals.append("Heuristic: review dates or volume/issue without proceedings → Journal")
            # Try to find journal in database
            if venue_name:
                journal_info = self.journal_db.lookup_by_name(venue_name)
                if journal_info:
                    signals.append(f"Found in SJR database: {journal_info.get('title')}")
                    return {
                        'title': parsed.get('title', 'Unknown Title'),
                        'category': 'journal',
                        'venue': journal_info.get('title', venue_name),
                        'quartile': journal_info.get('best_quartile', 'Unranked'),
                        'sjr_score': round(journal_info.get('sjr_score', 0), 3),
                        'is_arxiv': False,
                        'arxiv_id': None,
                        'conference_type': None,
                        'core_rank': None,
                        'suggested_journals': [],
                        'confidence': 0.65,
                        'signals': signals,
                        'doi': parsed.get('doi'),
                        'page_count': parsed.get('page_count', 0),
                        'keywords': parsed.get('keywords'),
                        'publisher': journal_info.get('publisher'),
                        'categories': journal_info.get('categories'),
                        'quartile_color': JournalDB.get_quartile_color(journal_info.get('best_quartile'))
                    }
            return {
                'title': parsed.get('title', 'Unknown Title'),
                'category': 'journal',
                'venue': venue_name or 'Unknown Journal',
                'quartile': 'Unranked',
                'sjr_score': None,
                'is_arxiv': False,
                'arxiv_id': None,
                'conference_type': None,
                'core_rank': None,
                'suggested_journals': [],
                'confidence': 0.55,
                'signals': signals,
                'doi': parsed.get('doi'),
                'page_count': parsed.get('page_count', 0),
                'keywords': parsed.get('keywords'),
                'publisher': None,
                'categories': None,
                'quartile_color': None
            }

        if has_proc or has_ieee:
            conference_type = self._determine_conference_type(parsed, venue_name, signals)
            signals.append(f"Heuristic: proceedings/IEEE keywords → Conference ({conference_type})")
            return {
                'title': parsed.get('title', 'Unknown Title'),
                'category': 'conference',
                'venue': venue_name or 'Unknown Conference',
                'quartile': None,
                'sjr_score': None,
                'is_arxiv': False,
                'arxiv_id': None,
                'conference_type': conference_type,
                'core_rank': None,
                'core_rank_description': None,
                'suggested_journals': [],
                'confidence': 0.55,
                'signals': signals,
                'doi': parsed.get('doi'),
                'page_count': parsed.get('page_count', 0),
                'keywords': parsed.get('keywords'),
                'publisher': None,
                'categories': None,
                'quartile_color': None
            }

        # Cannot determine
        signals.append("Could not determine paper type with sufficient confidence")
        return {
            'title': parsed.get('title', 'Unknown Title'),
            'category': 'unknown',
            'venue': venue_name or 'Unknown',
            'quartile': None,
            'sjr_score': None,
            'is_arxiv': False,
            'arxiv_id': None,
            'conference_type': None,
            'core_rank': None,
            'suggested_journals': [],
            'confidence': 0.30,
            'signals': signals,
            'doi': parsed.get('doi'),
            'page_count': parsed.get('page_count', 0),
            'keywords': parsed.get('keywords'),
            'publisher': None,
            'categories': None,
            'quartile_color': None
        }

    def _determine_conference_type(self, parsed: Dict, venue_name: str,
                                   signals: List[str]) -> str:
        """Determine if a conference is IEEE, International, or National."""
        text = parsed.get('full_text', '')
        combined = (text[:3000] + ' ' + venue_name).lower()
        doi = parsed.get('doi', '') or ''

        # Check for IEEE
        if ('ieee' in combined or
            '10.1109/' in doi.lower() or
            parsed.get('has_ieee_copyright', False) or
            bool(re.search(r'\$31\.00\s*©?\s*\d{4}\s*ieee', combined))):
            signals.append("IEEE indicators found (copyright, DOI prefix, or keyword)")
            return 'IEEE'

        # Check for National
        national_keywords = [
            'national conference', 'national symposium', 'national workshop',
            'all-india', 'all india', 'national convention',
            'national seminar'
        ]
        for keyword in national_keywords:
            if keyword in combined:
                signals.append(f"National conference keyword found: '{keyword}'")
                return 'National'

        # Default to International
        signals.append("No IEEE/National indicators → classified as International")
        return 'International'

    def _extract_field(self, parsed: Dict, s2_data: Dict) -> str:
        """Extract the research field from the paper for journal suggestions."""
        # Try Semantic Scholar fields of study
        fields_of_study = s2_data.get('fieldsOfStudy', [])
        if fields_of_study:
            return fields_of_study[0]

        # Try keywords
        keywords = parsed.get('keywords', '')
        if keywords:
            # Return first meaningful keyword
            keyword_list = [k.strip() for k in keywords.replace(';', ',').split(',')]
            if keyword_list:
                return keyword_list[0]

        # Try to infer from full text (look for common CS fields)
        text = parsed.get('full_text', '').lower()
        field_keywords = {
            'Computer Science': ['algorithm', 'computing', 'software', 'programming'],
            'Machine Learning': ['machine learning', 'deep learning', 'neural network', 'classification'],
            'Artificial Intelligence': ['artificial intelligence', 'reinforcement learning', 'natural language'],
            'Computer Vision': ['image processing', 'object detection', 'computer vision', 'image recognition'],
            'Data Science': ['data mining', 'big data', 'data analysis', 'analytics'],
            'Cybersecurity': ['security', 'encryption', 'cyber', 'malware', 'intrusion'],
            'Networks': ['network', 'wireless', 'iot', 'internet of things', '5g'],
            'Robotics': ['robot', 'autonomous', 'control system', 'sensor'],
            'Medicine': ['clinical', 'patient', 'disease', 'treatment', 'medical'],
            'Engineering': ['engineering', 'structural', 'mechanical', 'thermal'],
            'Physics': ['quantum', 'particle', 'physics', 'thermodynamics'],
            'Mathematics': ['theorem', 'proof', 'mathematical', 'equation'],
            'Biology': ['gene', 'protein', 'cell', 'biological', 'genome'],
            'Chemistry': ['chemical', 'molecular', 'compound', 'reaction'],
            'Environmental Science': ['climate', 'environmental', 'pollution', 'ecosystem'],
            'Economics': ['economic', 'market', 'financial', 'trade'],
        }

        best_field = 'Computer Science'  # default
        best_count = 0
        for field, keywords_list in field_keywords.items():
            count = sum(1 for kw in keywords_list if kw in text)
            if count > best_count:
                best_count = count
                best_field = field

        return best_field

    def _calculate_confidence(self, signals: List[str], category: str) -> float:
        """Calculate a confidence score based on the number and quality of signals."""
        base = 0.40
        signal_weights = {
            'DOI found': 0.10,
            'CrossRef type': 0.15,
            'Semantic Scholar venue': 0.10,
            'S2 venue type': 0.10,
            'ISSN match in SJR': 0.15,
            'Name match in SJR': 0.10,
            'CORE database match': 0.10,
            'Arxiv ID detected': 0.15,
            'Review dates found': 0.08,
            'Volume/Issue numbers': 0.05,
            'Conference/Proceedings': 0.08,
            'IEEE indicators': 0.08,
            'ISBN found': 0.05,
            'ISSN found': 0.05,
        }

        total = base
        for signal in signals:
            for key, weight in signal_weights.items():
                if key.lower() in signal.lower():
                    total += weight
                    break

        return round(min(total, 0.99), 2)

    def _error_result(self, message: str) -> Dict[str, Any]:
        """Return a standardized error result."""
        return {
            'title': 'Error',
            'category': 'error',
            'venue': None,
            'quartile': None,
            'sjr_score': None,
            'is_arxiv': False,
            'arxiv_id': None,
            'conference_type': None,
            'core_rank': None,
            'suggested_journals': [],
            'confidence': 0.0,
            'signals': [message],
            'doi': None,
            'page_count': 0,
            'keywords': None,
            'publisher': None,
            'categories': None,
            'quartile_color': None,
            'error': message,
            'authors': None,
            'abstract': None,
            'citation_count': None,
            'year': None,
            'fields_of_study': None
        }

    def close(self):
        """Close all database connections."""
        self.journal_db.close()
        self.conference_db.close()
