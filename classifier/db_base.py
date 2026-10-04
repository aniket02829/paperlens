"""Shared read-only SQLite access for the journal and conference lookups."""
import re
import sqlite3
import difflib
import threading
from typing import Dict, List, Optional


def name_key(name: str) -> str:
    """Normalize a venue name so small spelling differences still match.

    'The Journal of Physics & Chemistry.' -> 'journal of physics and chemistry'
    """
    if not name:
        return ''
    key = name.lower().replace('&', ' and ')
    key = re.sub(r'[^a-z0-9 ]+', ' ', key)
    key = re.sub(r'\s+', ' ', key).strip()
    if key.startswith('the '):
        key = key[4:]
    return key


class ReadOnlyDB:
    """Opens one read-only connection per thread, so concurrent requests are safe."""

    # Subclasses set these to build the in-memory name index used for fuzzy matching.
    TABLE = ''
    TITLE_COLUMN = 'title'
    # Words dropped before matching names; conferences set this so that
    # 'International Conference on X' matches 'X'.
    FILLER_WORDS: frozenset = frozenset()
    # Optional SQL condition limiting which rows are in the name index.
    INDEX_WHERE = ''

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        self._index_lock = threading.Lock()
        self._name_index: Optional[Dict[str, int]] = None
        self._name_keys: List[str] = []

    @property
    def conn(self) -> sqlite3.Connection:
        conn = getattr(self._local, 'conn', None)
        if conn is None:
            conn = sqlite3.connect(f'file:{self.db_path}?mode=ro', uri=True)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def query(self, sql: str, params=()) -> List[Dict]:
        return [dict(r) for r in self.conn.execute(sql, params).fetchall()]

    def query_one(self, sql: str, params=()) -> Optional[Dict]:
        row = self.conn.execute(sql, params).fetchone()
        return dict(row) if row else None

    def index_key(self, name: str) -> str:
        key = name_key(name)
        if self.FILLER_WORDS:
            key = ' '.join(w for w in key.split() if w not in self.FILLER_WORDS)
        return key

    def _ensure_name_index(self) -> None:
        if self._name_index is not None:
            return
        with self._index_lock:
            if self._name_index is not None:
                return
            index: Dict[str, int] = {}
            where = f'WHERE {self.INDEX_WHERE}' if self.INDEX_WHERE else ''
            rows = self.conn.execute(
                f'SELECT id, {self.TITLE_COLUMN} FROM {self.TABLE} {where} ORDER BY id'
            ).fetchall()
            for row in rows:
                key = self.index_key(row[1])
                if key and key not in index:
                    index[key] = row[0]
            self._name_keys = list(index)
            self._name_index = index

    def find_id_by_name(self, name: str, cutoff: float = 0.85, fuzzy: bool = True) -> Optional[int]:
        """Return the row id whose title best matches name, exact first, then fuzzy.

        fuzzy=False accepts only the exact normalised name: similar names belong to
        different venues ('Journal of Open Source Software' is not 'Journal of Open
        Research Software'), so callers that already know the venue's ISSN failed to
        match should not guess.
        """
        key = self.index_key(name)
        if not key:
            return None
        self._ensure_name_index()
        if key in self._name_index:
            return self._name_index[key]
        if not fuzzy:
            return None
        matches = difflib.get_close_matches(key, self._name_keys, n=1, cutoff=cutoff)
        return self._name_index[matches[0]] if matches else None

    def find_in_text(self, text: str, min_words: int = 2) -> Optional[int]:
        """Return the id of the venue whose name appears inside text (longest name wins).

        Names shorter than min_words are ignored: 'Science' or 'Cell' would match
        almost any sentence, 'Canadian Journal of Sociology' does not.
        """
        haystack = f' {self.index_key(text or "")} '
        if not haystack.strip():
            return None
        self._ensure_name_index()
        best = None
        for key in self._name_keys:
            if len(key.split()) >= min_words and f' {key} ' in haystack and (best is None or len(key) > len(best)):
                best = key
        return self._name_index[best] if best else None

    def close(self):
        conn = getattr(self._local, 'conn', None)
        if conn is not None:
            conn.close()
            self._local.conn = None
