"""Database operations for Journal matching."""
import sqlite3
import difflib
from typing import Optional, List, Dict

class JournalDB:
    """Handles lookups and queries against the journals database."""
    def __init__(self, db_path: str):
        """Initialize the database connection.
        
        Args:
            db_path: Path to the SQLite database.
        """
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def lookup_by_issn(self, issn: str) -> Optional[Dict]:
        """Look up a journal by its ISSN.
        
        Args:
            issn: The ISSN string to look up.
            
        Returns:
            Dictionary containing journal data, or None if not found.
        """
        normalized_issn = issn.replace('-', '').replace(' ', '')
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT j.* FROM journals j
            JOIN journal_issns ji ON j.id = ji.journal_id
            WHERE ji.issn = ?
        ''', (normalized_issn,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def lookup_by_name(self, name: str) -> Optional[Dict]:
        """Look up a journal by exact normalized name, then fuzzy match.
        
        Args:
            name: The journal name to look up.
            
        Returns:
            Dictionary containing journal data, or None if not found.
        """
        normalized_name = name.strip().lower()
        cursor = self.conn.cursor()
        
        # Exact match
        cursor.execute('''
            SELECT * FROM journals WHERE title_normalized = ? LIMIT 1
        ''', (normalized_name,))
        row = cursor.fetchone()
        if row:
            return dict(row)
            
        # Fuzzy match
        cursor.execute('SELECT title_normalized FROM journals')
        all_titles = [r['title_normalized'] for r in cursor.fetchall() if r['title_normalized']]
        
        matches = difflib.get_close_matches(normalized_name, all_titles, n=1, cutoff=0.85)
        if matches:
            best_match = matches[0]
            cursor.execute('''
                SELECT * FROM journals WHERE title_normalized = ? LIMIT 1
            ''', (best_match,))
            row = cursor.fetchone()
            if row:
                return dict(row)
                
        return None

    def suggest_journals(self, field: str, top_n: int = 10) -> List[Dict]:
        """Return top N journals by SJR score in a specific field/category.
        
        Args:
            field: The category keyword to search for.
            top_n: Number of journals to return.
            
        Returns:
            List of dictionaries containing journal data.
        """
        cursor = self.conn.cursor()
        query = f"%{field}%"
        cursor.execute('''
            SELECT * FROM journals
            WHERE categories LIKE ? OR areas LIKE ?
            ORDER BY sjr_score DESC
            LIMIT ?
        ''', (query, query, top_n))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def get_quartile_color(quartile: str) -> str:
        """Return color associated with a quartile.
        
        Args:
            quartile: Quartile string (e.g., 'Q1').
            
        Returns:
            Color string.
        """
        if not quartile:
            return 'gray'
            
        quartile_upper = str(quartile).strip().upper()
        if 'Q1' in quartile_upper:
            return 'green'
        elif 'Q2' in quartile_upper:
            return 'blue'
        elif 'Q3' in quartile_upper:
            return 'yellow'
        elif 'Q4' in quartile_upper:
            return 'red'
        return 'gray'

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
