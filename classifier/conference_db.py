"""Database operations for Conference matching."""
import sqlite3
import difflib
from typing import Optional, Dict

class ConferenceDB:
    """Handles lookups and queries against the conferences database."""
    def __init__(self, db_path: str):
        """Initialize the database connection.
        
        Args:
            db_path: Path to the SQLite database.
        """
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def lookup_by_acronym(self, acronym: str) -> Optional[Dict]:
        """Look up a conference by its acronym.
        
        Args:
            acronym: The conference acronym.
            
        Returns:
            Dictionary containing conference data, or None if not found.
        """
        normalized_acronym = acronym.strip().lower()
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM conferences
            WHERE acronym_normalized = ?
        ''', (normalized_acronym,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def lookup_by_name(self, name: str) -> Optional[Dict]:
        """Look up a conference by exact normalized name, then fuzzy match.
        
        Args:
            name: The conference name.
            
        Returns:
            Dictionary containing conference data, or None if not found.
        """
        normalized_name = name.strip().lower()
        cursor = self.conn.cursor()
        
        # Exact match
        cursor.execute('''
            SELECT * FROM conferences WHERE title_normalized = ? LIMIT 1
        ''', (normalized_name,))
        row = cursor.fetchone()
        if row:
            return dict(row)
            
        # Fuzzy match
        cursor.execute('SELECT title_normalized FROM conferences')
        all_titles = [r['title_normalized'] for r in cursor.fetchall() if r['title_normalized']]
        
        matches = difflib.get_close_matches(normalized_name, all_titles, n=1, cutoff=0.85)
        if matches:
            best_match = matches[0]
            cursor.execute('''
                SELECT * FROM conferences WHERE title_normalized = ? LIMIT 1
            ''', (best_match,))
            row = cursor.fetchone()
            if row:
                return dict(row)
                
        return None

    @staticmethod
    def get_rank_description(rank: str) -> str:
        """Return a descriptive string for a conference rank.
        
        Args:
            rank: The conference rank string (e.g., 'A*').
            
        Returns:
            Description of the rank.
        """
        if not rank:
            return 'Not Ranked'
            
        rank_upper = str(rank).strip().upper()
        descriptions = {
            'A*': 'Flagship/Top-tier',
            'A': 'Excellent',
            'B': 'Good',
            'C': 'Average'
        }
        return descriptions.get(rank_upper, 'Not Ranked')

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
