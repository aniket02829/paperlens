import { useEffect, useRef } from 'react';
import { GlowCard } from '../../components/GlowCard';
import { m } from 'motion/react';
import { csvCell, downloadText, percent } from '../../lib/format';
import { t } from '../../lib/strings';
import { Button, CategoryBadge } from '../../components/ui';
import type { BulkResponse, PaperResult } from '../../types';

function exportCsv(results: PaperResult[]) {
  const header = ['File', 'Title', 'Category', 'Venue', 'Quartile', 'SJR', 'CORE rank', 'Conference type', 'DOI', 'Year', 'Confidence'];
  const rows = results.map(r => [r.filename, r.title, r.category, r.venue, r.quartile, r.sjr_score, r.core_rank,
    r.conference_type, r.doi, r.year, `${percent(r.confidence)}%`]);
  downloadText('paperlens_results.csv', [header, ...rows].map(row => row.map(csvCell).join(',')).join('\r\n'), 'text/csv;charset=utf-8');
}

export function BulkResult({ data, onReset }: { data: BulkResponse; onReset: () => void }) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    headingRef.current?.focus({ preventScroll: true });
    headingRef.current?.closest('section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [data]);
  const s = data.summary;
  const stats = [
    { label: t('catJournal'), value: s.journals, cls: 'bg-journal-soft text-journal' },
    { label: t('catConference'), value: s.conferences, cls: 'bg-conference-soft text-conference' },
    { label: t('catPreprint'), value: s.arxiv, cls: 'bg-preprint-soft text-preprint' },
    { label: t('bulkUnclear'), value: s.unknown + s.failed, cls: 'bg-surface-2 text-fg' },
  ];
  return (
    <m.section initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
      className="scroll-mt-24" aria-labelledby="bulkHeading">
      <GlowCard innerClassName="p-5 sm:p-8">
      <h2 id="bulkHeading" ref={headingRef} tabIndex={-1} className="text-display-sm font-semibold focus:outline-none">{t('bulkTitle', { n: s.total })}</h2>
      <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {stats.map(stat => (
          <div key={stat.label} className={`rounded-md p-4 ${stat.cls}`}>
            <p className="text-sm font-bold">{stat.label}</p>
            <p className="font-serif text-3xl font-semibold">{stat.value}</p>
          </div>
        ))}
      </div>
      {data.results.length > 0 && (
        <div className="mt-6 overflow-x-auto rounded-md border border-border">
          <table className="table-base">
            <caption className="sr-only">{t('bulkTitle', { n: s.total })}</caption>
            <thead><tr>{[t('colPaper'), t('colType'), t('factVenue'), t('factRank'), t('colConfidence')].map(c => <th key={c} scope="col">{c}</th>)}</tr></thead>
            <tbody className="divide-y divide-border">
              {data.results.map((r, i) => {
                const rank = r.category === 'journal' ? r.quartile || t('unranked') : r.category === 'conference' ? (r.core_rank ? `CORE ${r.core_rank}` : t('unranked')) : '–';
                return (
                  <tr key={`${r.filename}-${i}`}>
                    <td className="max-w-[16rem]"><span className="block break-words font-bold">{r.title}</span><span className="block break-all text-xs text-muted">{r.filename}</span></td>
                    <td><CategoryBadge category={r.category} /></td>
                    <td className="max-w-[14rem] break-words">{r.venue || '–'}</td>
                    <td>{rank}</td>
                    <td className="font-bold">{percent(r.confidence)}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {data.errors.length > 0 && (
        <div className="mt-6">
          <h3 className="font-sans text-base font-bold">{t('bulkErrors')}</h3>
          <ul className="mt-2 space-y-1 text-sm">{data.errors.map((e, i) => <li key={i}><strong>{e.filename}: </strong>{e.error}</li>)}</ul>
        </div>
      )}
      <div className="no-print mt-8 flex flex-wrap gap-2 border-t border-border pt-6">
        {data.results.length > 0 && <Button icon="download" onClick={() => exportCsv(data.results)}>{t('exportCsv')}</Button>}
        <Button variant="primary" icon="reset" className="sm:ml-auto" onClick={onReset}>{t('newBatch')}</Button>
      </div>
      </GlowCard>
    </m.section>
  );
}
