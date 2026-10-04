import { t, type StringKey } from '../../lib/strings';
import type { PaperResult } from '../../types';

export function rankKey(rank: string | null): 'A*' | 'A' | 'B' | 'C' | 'NATIONAL' | null {
  const r = (rank || '').trim().toUpperCase();
  if (r === 'A*' || r === 'A' || r === 'B' || r === 'C') return r;
  if (r.startsWith('NATIONAL') || r.startsWith('REGIONAL') || r.startsWith('AUSTRALASIAN')) return 'NATIONAL';
  return null;
}

/** The one-line answer and its plain-language explanation. */
export function verdict(result: PaperResult): { headline: string; detail: string } {
  switch (result.category) {
    case 'journal': {
      const q = /^Q[1-4]$/.test(result.quartile || '') ? result.quartile! : null;
      if (result.scopus?.discontinued) {
        const year = result.scopus.discontinued_year ? ` in ${result.scopus.discontinued_year}` : '';
        return { headline: t('verdictJournalDiscontinued'), detail: t('explainJournalDiscontinued', { year }) };
      }
      if (q) return { headline: t('verdictJournalQ', { q }), detail: t(`explain${q}` as StringKey) };
      if (result.trust?.indexed_in_scopus) return { headline: t('verdictJournalScopusOnly'), detail: t('explainJournalScopusOnly') };
      return { headline: t('verdictJournalUnranked'), detail: t('explainJournalUnranked') };
    }
    case 'conference': {
      const key = rankKey(result.core_rank);
      if (key === 'NATIONAL') return { headline: t('verdictConfNational'), detail: t('explainNational') };
      return key
        ? { headline: t('verdictConfRank', { rank: key }), detail: t(`explainRank${key === 'A*' ? 'AStar' : key}` as StringKey) }
        : { headline: t('verdictConfUnranked'), detail: t('explainConfUnranked') };
    }
    case 'arxiv':
      return { headline: t('verdictPreprint'), detail: t('explainPreprint') };
    default:
      return { headline: t('verdictUnknown'), detail: result.error || t('explainUnknown') };
  }
}

export function rerunQuery(result: PaperResult, query: string | null): string | null {
  return query || result.doi || (result.arxiv_id ? `arXiv:${result.arxiv_id}` : null);
}
