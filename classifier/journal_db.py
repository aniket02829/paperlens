"""Database operations for Journal matching."""
from typing import Optional, List, Dict

from classifier.db_base import ReadOnlyDB

QUARTILES = ('Q1', 'Q2', 'Q3', 'Q4')


def like_pattern(text: str) -> str:
    """Wrap text in % for a LIKE query, escaping LIKE wildcards in the text itself."""
    escaped = text.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return f'%{escaped}%'


class JournalDB(ReadOnlyDB):
    """Handles lookups and queries against the journals database."""

    TABLE = 'journals'
    # Name matches are for journals only: 'Proceedings of Machine Learning Research' and
    # 'Lecture Notes in Computer Science' are in SJR but are not journals.
    INDEX_WHERE = "source_type = 'journal'"

    def lookup_by_issn(self, issn: str) -> Optional[Dict]:
        """Look up a journal by its ISSN (with or without the hyphen)."""
        normalized_issn = issn.replace('-', '').replace(' ', '').upper()
        return self.query_one('''
            SELECT j.* FROM journals j
            JOIN journal_issns ji ON j.id = ji.journal_id
            WHERE ji.issn = ?
        ''', (normalized_issn,))

    def lookup_by_name(self, name: str, fuzzy: bool = True) -> Optional[Dict]:
        """Look up a journal by normalized name, then (if fuzzy) by close match."""
        journal_id = self.find_id_by_name(name, fuzzy=fuzzy)
        return self.get_by_id(journal_id) if journal_id else None

    def find_in_text(self, text: str) -> Optional[Dict]:
        """The journal whose name is printed inside a header or copyright line.

        '© Canadian Journal of Sociology 46(3) 2021' -> Canadian Journal of Sociology.
        Three words minimum, so generic names cannot match by accident.
        """
        journal_id = super().find_in_text(text, min_words=3)
        return self.get_by_id(journal_id) if journal_id else None

    def get_by_id(self, journal_id: int) -> Optional[Dict]:
        return self.query_one('SELECT * FROM journals WHERE id = ?', (journal_id,))

    def get_by_ids(self, journal_ids: List[int]) -> List[Dict]:
        """Return journals in the same order as journal_ids, skipping unknown ids."""
        if not journal_ids:
            return []
        placeholders = ','.join('?' * len(journal_ids))
        rows = self.query(f'SELECT * FROM journals WHERE id IN ({placeholders})', journal_ids)
        by_id = {r['id']: r for r in rows}
        return [by_id[i] for i in journal_ids if i in by_id]

    def suggest_journals(self, field: str, top_n: int = 10) -> List[Dict]:
        """Return the top N ranked journals by SJR score whose categories or areas mention field.

        SJR also lists conference proceedings, book series and trade journals; those are
        left out because they are not journals you can submit a paper to.
        """
        query = like_pattern(field)
        return self.query('''
            SELECT * FROM journals
            WHERE (categories LIKE ? ESCAPE '\\' OR areas LIKE ? ESCAPE '\\')
              AND best_quartile IN ('Q1', 'Q2', 'Q3', 'Q4')
              AND source_type = 'journal'
            ORDER BY sjr_score DESC
            LIMIT ?
        ''', (query, query, top_n))

    def search(self, text: str = '', area: str = '', quartile: str = '',
               open_access: Optional[bool] = None, limit: int = 20,
               offset: int = 0) -> Dict:
        """Search journals by title, ISSN or subject category, with optional filters.

        Returns {'total': int, 'results': [journal, ...]} sorted by SJR score.
        """
        where, params = [], []
        text = (text or '').strip()
        if text:
            digits = text.replace('-', '').replace(' ', '').upper()
            if len(digits) == 8 and digits[:7].isdigit():
                where.append('id IN (SELECT journal_id FROM journal_issns WHERE issn = ?)')
                params.append(digits)
            else:
                pattern = like_pattern(text.lower())
                where.append("(title_normalized LIKE ? ESCAPE '\\' OR lower(categories) LIKE ? ESCAPE '\\')")
                params.extend([pattern, pattern])
        if area:
            where.append("areas LIKE ? ESCAPE '\\'")
            params.append(like_pattern(area))
        if quartile in QUARTILES:
            where.append('best_quartile = ?')
            params.append(quartile)
        if open_access is not None:
            where.append('open_access = ?')
            params.append('Yes' if open_access else 'No')

        clause = f"WHERE {' AND '.join(where)}" if where else ''
        total = self.conn.execute(f'SELECT COUNT(*) FROM journals {clause}', params).fetchone()[0]
        results = self.query(
            f'SELECT * FROM journals {clause} ORDER BY sjr_score DESC LIMIT ? OFFSET ?',
            params + [limit, offset]
        )
        return {'total': total, 'results': results}

    def list_areas(self) -> List[str]:
        """Return the sorted list of distinct subject areas (e.g. 'Computer Science')."""
        areas = set()
        for row in self.conn.execute('SELECT DISTINCT areas FROM journals'):
            for area in (row[0] or '').split(';'):
                if area.strip():
                    areas.add(area.strip())
        return sorted(areas)

    def count(self) -> int:
        return self.conn.execute('SELECT COUNT(*) FROM journals').fetchone()[0]

    @staticmethod
    def get_quartile_color(quartile: str) -> str:
        """Return the color associated with a quartile ('Q1' -> 'green')."""
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
