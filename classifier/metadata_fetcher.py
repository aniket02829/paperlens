"""
API fetcher layer for gathering research paper metadata from external APIs.
"""
import requests
import logging
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class MetadataFetcher:
    """Fetches metadata from external APIs like CrossRef and Semantic Scholar."""
    
    def __init__(self, crossref_email: str, semantic_scholar_api_key: Optional[str] = None):
        """
        Initialize the MetadataFetcher.
        
        Args:
            crossref_email: Email to use for polite pool in CrossRef API.
            semantic_scholar_api_key: Optional API key for Semantic Scholar.
        """
        self.crossref_email = crossref_email
        self.semantic_scholar_api_key = semantic_scholar_api_key
        self.timeout = 5
        self.s2_last_call_time = 0.0

    def fetch_by_doi(self, doi: str) -> Dict[str, Any]:
        """
        Fetch metadata from CrossRef API using DOI.
        
        Args:
            doi: The DOI of the paper.
            
        Returns:
            Dictionary with extracted metadata or empty dictionary on failure.
        """
        url = f"https://api.crossref.org/works/{doi}"
        headers = {
            "User-Agent": f"PaperClassifierApp/1.0 (mailto:{self.crossref_email})"
        }
        
        try:
            logger.info(f"Fetching metadata for DOI: {doi}")
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json().get('message', {})
            
            published = data.get('published-print') or data.get('published-online') or data.get('issued') or {}
            year = published.get('date-parts', [[None]])[0][0] if published else None
            
            result = {
                'type': data.get('type'),
                'container-title': data.get('container-title', [None])[0] if data.get('container-title') else None,
                'issn': data.get('ISSN', []),
                'publisher': data.get('publisher'),
                'volume': data.get('volume'),
                'issue': data.get('issue'),
                'year': year
            }
            return {k: v for k, v in result.items() if v is not None}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching from CrossRef for DOI {doi}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error in fetch_by_doi: {e}")
            return {}

    def fetch_by_title(self, title: str) -> Dict[str, Any]:
        """
        Search CrossRef API by title and return the best match.
        
        Args:
            title: The title of the paper.
            
        Returns:
            Dictionary with metadata of the best match or empty dictionary.
        """
        url = "https://api.crossref.org/works"
        params = {
            "query.title": title,
            "rows": 3,
            "select": "type,container-title,ISSN,publisher,volume,issue,score,published-print,published-online,issued"
        }
        headers = {
            "User-Agent": f"PaperClassifierApp/1.0 (mailto:{self.crossref_email})"
        }
        
        try:
            logger.info(f"Fetching metadata for title: {title}")
            response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            items = response.json().get('message', {}).get('items', [])
            if not items:
                return {}
                
            # Items are typically sorted by score in the API response, take the first one
            best_match = items[0]
            
            published = best_match.get('published-print') or best_match.get('published-online') or best_match.get('issued') or {}
            year = published.get('date-parts', [[None]])[0][0] if published else None
            
            result = {
                'type': best_match.get('type'),
                'container-title': best_match.get('container-title', [None])[0] if best_match.get('container-title') else None,
                'issn': best_match.get('ISSN', []),
                'publisher': best_match.get('publisher'),
                'volume': best_match.get('volume'),
                'issue': best_match.get('issue'),
                'year': year
            }
            return {k: v for k, v in result.items() if v is not None}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching from CrossRef for title '{title}': {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error in fetch_by_title: {e}")
            return {}

    def fetch_semantic_scholar(self, identifier: str) -> Dict[str, Any]:
        """
        Fetch metadata from Semantic Scholar API.
        
        Args:
            identifier: S2 paper ID, DOI, or arXiv ID.
            
        Returns:
            Dictionary with metadata or empty dictionary.
        """
        # Rate limiting: wait if less than 1 second has passed since last call
        elapsed = time.time() - self.s2_last_call_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
            
        # Determine the format of the identifier
        if identifier.lower().startswith("arxiv:"):
            query_id = f"ARXIV:{identifier[6:]}"
        elif identifier.startswith("10."):
            query_id = f"DOI:{identifier}"
        else:
            query_id = identifier
            
        url = f"https://api.semanticscholar.org/graph/v1/paper/{query_id}"
        params = {
            "fields": "title,venue,publicationVenue,year,citationCount,externalIds,authors,abstract,fieldsOfStudy"
        }
        headers = {}
        if self.semantic_scholar_api_key:
            headers['x-api-key'] = self.semantic_scholar_api_key
            
        try:
            logger.info(f"Fetching metadata from Semantic Scholar for: {query_id}")
            self.s2_last_call_time = time.time()
            response = requests.get(url, params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching from Semantic Scholar for '{identifier}': {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error in fetch_semantic_scholar: {e}")
            return {}

    def fetch_paper_details(self, doi_or_arxiv_id: str) -> Dict[str, Any]:
        """
        Fetches and combines details from CrossRef and Semantic Scholar.
        
        Args:
            doi_or_arxiv_id: DOI or arXiv ID of the paper.
            
        Returns:
            Dictionary with enriched metadata.
        """
        details = {
            'title': None,
            'authors': None,
            'year': None,
            'citation_count': None,
            'abstract': None,
            'venue': None,
            'fields_of_study': None
        }
        
        # Determine if DOI or arXiv
        is_doi = doi_or_arxiv_id.startswith("10.")
        
        # Fetch data
        crossref_data = {}
        if is_doi:
            crossref_data = self.fetch_by_doi(doi_or_arxiv_id)
            
        s2_data = self.fetch_semantic_scholar(doi_or_arxiv_id)
        
        # Combine data
        if s2_data:
            details['title'] = s2_data.get('title')
            
            # Extract authors from S2
            s2_authors = s2_data.get('authors', [])
            if s2_authors:
                details['authors'] = ', '.join([a.get('name', '') for a in s2_authors if a.get('name')])
                
            details['year'] = s2_data.get('year')
            details['citation_count'] = s2_data.get('citationCount')
            details['abstract'] = s2_data.get('abstract')
            details['venue'] = s2_data.get('venue')
            
            fields = s2_data.get('fieldsOfStudy', [])
            if fields:
                details['fields_of_study'] = ', '.join(fields)
                
        # Fill in missing details from CrossRef if available
        if crossref_data:
            if not details['venue'] and crossref_data.get('container-title'):
                details['venue'] = crossref_data.get('container-title')
                
        return details
