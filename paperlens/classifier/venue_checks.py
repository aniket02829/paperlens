"""Checks on a venue's indexing and reputation, from the public lists in the database.

    Scopus source list        is the journal indexed in Scopus, still active, or discontinued?
    DOAJ                      is the journal in the Directory of Open Access Journals (fees, review)?
    Hijacked Journal Checker  does a fake clone of this journal exist? (Retraction Watch)
    Stop Predatory Journals   is the journal or publisher name on a community predatory list?

Every method takes the ISSNs and names already gathered for the paper and returns a
plain dict (or None), so the classifier can attach it to the result unchanged. Matches by
name are exact after normalisation: a fuzzy match could accuse the wrong journal.
"""
import re
from typing import Dict, Iterable, List, Optional

from classifier.db_base import ReadOnlyDB, name_key


def normalize_issn(issn: str) -> str:
    return re.sub(r'[^0-9X]', '', (issn or '').upper())


def _clean(values: Iterable[Optional[str]], transform) -> List[str]:
    out: List[str] = []
    for value in values:
        key = transform(value or '')
        if key and key not in out:
            out.append(key)
    return out


class VenueChecksDB(ReadOnlyDB):
    """Read-only lookups in the doaj_*, scopus_sources and watchlist tables."""

    def editions(self) -> Dict[str, str]:
        """Which edition of each list the database was built from."""
        try:
            return {row['key']: row['value'] for row in self.query('SELECT key, value FROM meta')}
        except Exception:
            return {}

    # ------------------------------------------------------------------ Scopus

    def scopus(self, issns: Iterable[Optional[str]], names: Iterable[Optional[str]]) -> Optional[Dict]:
        """Scopus indexing status for a journal, by ISSN first, then by exact title."""
        row = None
        for issn in _clean(issns, normalize_issn):
            if len(issn) != 8:
                continue
            row = self.query_one('SELECT * FROM scopus_sources WHERE issn = ? OR eissn = ? '
                                 'ORDER BY active DESC, discontinued ASC LIMIT 1', (issn, issn))
            if row:
                break
        if not row:
            for name in _clean(names, name_key):
                row = self.query_one('SELECT * FROM scopus_sources WHERE title_normalized = ? '
                                     'ORDER BY active DESC, discontinued ASC LIMIT 1', (name,))
                if row:
                    break
        if not row:
            return None
        return {
            'title': row['title'],
            'source_type': row['source_type'],
            'active': bool(row['active']),
            'discontinued': bool(row['discontinued']),
            'discontinued_year': row['discontinued_year'] or None,
            'discontinued_reason': row['discontinued_reason'] or None,
            'coverage': row['coverage'] or None,
        }

    # ------------------------------------------------------------------ DOAJ

    def doaj(self, issns: Iterable[Optional[str]], names: Iterable[Optional[str]]) -> Optional[Dict]:
        row = None
        for issn in _clean(issns, normalize_issn):
            if len(issn) != 8:
                continue
            row = self.query_one('SELECT j.* FROM doaj_journals j JOIN doaj_issns i ON i.journal_id = j.id '
                                 'WHERE i.issn = ? LIMIT 1', (issn,))
            if row:
                break
        if not row:
            for name in _clean(names, name_key):
                row = self.query_one('SELECT * FROM doaj_journals WHERE title_normalized = ? LIMIT 1', (name,))
                if row:
                    break
        if not row:
            return None
        return {
            'title': row['title'],
            'url': row['url'] or None,
            'apc': row['apc'] or None,                       # 'Yes' / 'No'
            'apc_amount': row['apc_amount'] or None,         # e.g. '1500 USD'
            'review_process': row['review_process'] or None,
            'weeks_to_publication': row['weeks_to_publication'] or None,
            'license': row['license'] or None,
            'added_on': row['added_on'] or None,
        }

    # ------------------------------------------------------------------ watchlists

    def hijacked(self, issns: Iterable[Optional[str]], names: Iterable[Optional[str]]) -> Optional[Dict]:
        """A known hijacked clone of this journal, matched by ISSN (clone or original) or name."""
        row = None
        for issn in _clean(issns, normalize_issn):
            if len(issn) != 8:
                continue
            row = self.query_one("SELECT w.* FROM watchlist w JOIN watchlist_issns i ON i.watchlist_id = w.id "
                                 "WHERE w.kind = 'hijacked' AND i.issn = ? LIMIT 1", (issn,))
            if row:
                break
        if not row:
            for name in _clean(names, name_key):
                row = self.query_one("SELECT * FROM watchlist WHERE kind = 'hijacked' AND "
                                     "(name_normalized = ? OR authentic_name = ?) LIMIT 1", (name, name))
                if row:
                    break
        if not row:
            return None
        return {
            'clone_name': row['name'],
            'clone_url': row['url'] or None,
            'authentic_name': row['authentic_name'] or row['name'],
            'authentic_url': row['authentic_url'] or None,
            'source': row['source'],
        }

    def predatory(self, names: Iterable[Optional[str]], publishers: Iterable[Optional[str]]) -> Dict[str, Optional[Dict]]:
        """Exact-name matches on the community predatory lists, for the journal and its publisher."""
        out: Dict[str, Optional[Dict]] = {'journal': None, 'publisher': None}
        for kind, values in (('predatory_journal', names), ('predatory_publisher', publishers)):
            for name in _clean(values, name_key):
                row = self.query_one('SELECT * FROM watchlist WHERE kind = ? AND name_normalized = ? LIMIT 1',
                                     (kind, name))
                if row:
                    out['journal' if kind == 'predatory_journal' else 'publisher'] = {
                        'name': row['name'], 'url': row['url'] or None, 'source': row['source']}
                    break
        return out

    def counts(self) -> Dict[str, int]:
        return {
            'scopus_sources': self.conn.execute('SELECT COUNT(*) FROM scopus_sources').fetchone()[0],
            'doaj_journals': self.conn.execute('SELECT COUNT(*) FROM doaj_journals').fetchone()[0],
            'hijacked_journals': self.conn.execute("SELECT COUNT(*) FROM watchlist WHERE kind = 'hijacked'").fetchone()[0],
            'predatory_entries': self.conn.execute("SELECT COUNT(*) FROM watchlist WHERE kind != 'hijacked'").fetchone()[0],
        }
