"""Database operations for Conference matching."""
from typing import Optional, Dict

from classifier.db_base import ReadOnlyDB

# Book series printed on conference papers; their names must not be read as a
# conference name ("Proceedings of Machine Learning Research" is not ICML).
SERIES_NAMES = ('proceedings of machine learning research', 'lecture notes in computer science',
                'lecture notes in artificial intelligence', 'communications in computer and information science')


class ConferenceDB(ReadOnlyDB):
    """Handles lookups and queries against the CORE conferences database."""

    TABLE = 'conferences'
    FILLER_WORDS = frozenset({'international', 'conference', 'conferences', 'proceedings', 'annual',
                              'on', 'the', 'of', 'and', 'for', 'in', 'ieee', 'acm', 'cvf', 'joint'})

    def lookup_by_acronym(self, acronym: str) -> Optional[Dict]:
        """Look up a conference by its acronym (case-insensitive)."""
        return self.query_one(
            'SELECT * FROM conferences WHERE acronym_normalized = ? LIMIT 1',
            (acronym.strip().lower(),)
        )

    def lookup_by_name(self, name: str) -> Optional[Dict]:
        """Look up a conference by normalized name, then by fuzzy match."""
        conference_id = self.find_id_by_name(name)
        if not conference_id:
            return None
        return self.query_one('SELECT * FROM conferences WHERE id = ?', (conference_id,))

    def find_in_text(self, text: str) -> Optional[Dict]:
        """Find the CORE conference whose name appears inside text (longest name wins).

        Used for venue lines read from a PDF, which carry extra words such as the
        edition, city and year: 'Proceedings of the 40th International Conference on
        Machine Learning, Honolulu, Hawaii, USA. PMLR 202, 2023'.
        """
        lowered = (text or '').lower()
        for series in SERIES_NAMES:
            lowered = lowered.replace(series, ' ')
        conference_id = super().find_in_text(lowered, min_words=2)
        if conference_id is None:
            return None
        return self.query_one('SELECT * FROM conferences WHERE id = ?', (conference_id,))

    def count(self) -> int:
        return self.conn.execute('SELECT COUNT(*) FROM conferences').fetchone()[0]

    @staticmethod
    def is_national_rank(rank: str) -> bool:
        """CORE marks national and regional events with ranks like 'National: India'."""
        rank_lower = (rank or '').strip().lower()
        return rank_lower.startswith('national') or rank_lower.startswith('regional')

    @staticmethod
    def get_rank_description(rank: str) -> str:
        """Return a plain-language description of a CORE rank (e.g. 'A*')."""
        if not rank:
            return 'Not Ranked'
        rank_upper = str(rank).strip().upper()
        descriptions = {
            'A*': 'Flagship/Top-tier',
            'A': 'Excellent',
            'B': 'Good',
            'C': 'Average'
        }
        if rank_upper in descriptions:
            return descriptions[rank_upper]
        if ConferenceDB.is_national_rank(rank):
            return 'National/Regional'
        if rank_upper.startswith('AUSTRALASIAN'):
            return 'Regional (Australasia)'
        if 'JOURNAL' in rank_upper:
            return 'Published as a journal'
        return 'Not Ranked'
