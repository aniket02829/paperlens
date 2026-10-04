import { useEffect, useState, type FormEvent } from 'react';
import { GlowCard } from '../components/GlowCard';
import { AnimatePresence, m } from 'motion/react';
import { api } from '../lib/api';
import { formatNumber } from '../lib/format';
import { t } from '../lib/strings';
import { Icon } from '../components/Icon';
import { Button, EmptyState, QuartilePill } from '../components/ui';
import { useCompare } from '../state/compare';
import type { Journal, JournalSearchResponse } from '../types';

export function CompareToggle({ journal, compact = false }: { journal: Pick<Journal, 'id' | 'title'>; compact?: boolean }) {
  const { has, toggle } = useCompare();
  const added = has(journal.id);
  return (
    <button type="button" aria-pressed={added} onClick={() => toggle(journal.id)}
      className={compact ? 'btn-ghost min-h-[36px] px-2 text-xs' : added ? 'btn border border-primary-text bg-primary-soft text-primary-text' : 'btn-secondary'}>
      <Icon name={added ? 'check' : 'plus'} />{added ? t('inCompare') : t('addCompare')}<span className="sr-only">: {journal.title}</span>
    </button>
  );
}

const list = { hidden: {}, show: { transition: { staggerChildren: 0.035 } } };
const item = { hidden: { opacity: 0, y: 8 }, show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.22, 1, 0.36, 1] as const } } };

export function JournalsView() {
  const [areas, setAreas] = useState<string[]>([]);
  const [q, setQ] = useState('');
  const [area, setArea] = useState('');
  const [quartile, setQuartile] = useState('');
  const [oa, setOa] = useState(false);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<JournalSearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<{ areas: string[] }>('/api/journals/areas').then(r => setAreas(r.areas)).catch(() => {});
  }, []);

  const search = async (nextPage: number) => {
    const params = new URLSearchParams({ q: q.trim(), area, quartile, page: String(nextPage), per_page: '20' });
    if (oa) params.set('oa', '1');
    setLoading(true);
    setError(null);
    try {
      setData(await api<JournalSearchResponse>(`/api/journals/search?${params}`));
      setPage(nextPage);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = (e: FormEvent) => { e.preventDefault(); search(1); };
  const pages = data ? Math.max(1, Math.ceil(data.total / data.per_page)) : 1;

  return (
    <div className="container-page max-w-5xl py-12">
      <p className="eyebrow">Scimago Journal Rank</p>
      <h1 className="mt-2 text-display-sm font-semibold sm:text-display-md">Journal search</h1>
      <p className="mt-3 max-w-2xl text-muted">Search more than 32,000 journals ranked by Scimago, to select a journal for submission or to verify a journal’s standing.</p>

      <form onSubmit={onSubmit} noValidate className="card mt-8 grid gap-4 p-4 sm:grid-cols-12 sm:p-6">
        <div className="sm:col-span-12">
          <label htmlFor="jq" className="label">Journal name, ISSN, or subject</label>
          <input id="jq" type="search" className="input" placeholder="e.g. machine learning, 0031-3203, Lancet" autoComplete="off" value={q} onChange={e => setQ(e.target.value)} />
        </div>
        <div className="sm:col-span-5">
          <label htmlFor="jarea" className="label">Subject area</label>
          <select id="jarea" className="input" value={area} onChange={e => setArea(e.target.value)}>
            <option value="">All subject areas</option>
            {areas.map(a => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
        <div className="sm:col-span-3">
          <label htmlFor="jquartile" className="label">Quartile</label>
          <select id="jquartile" className="input" value={quartile} onChange={e => setQuartile(e.target.value)}>
            <option value="">All quartiles</option>
            {['Q1', 'Q2', 'Q3', 'Q4'].map(x => <option key={x} value={x}>{x}</option>)}
          </select>
        </div>
        <div className="flex items-end sm:col-span-4">
          <label className="flex min-h-[44px] cursor-pointer items-center gap-2 text-sm font-bold">
            <input type="checkbox" className="h-5 w-5 rounded border-border-strong accent-[rgb(var(--primary))]" checked={oa} onChange={e => setOa(e.target.checked)} />
            Open access only
          </label>
        </div>
        <div className="sm:col-span-12">
          <Button type="submit" variant="primary" icon="search" className="w-full px-6 sm:w-auto" disabled={loading}>Search</Button>
        </div>
      </form>

      <p className="mt-8 font-bold" role="status" aria-live="polite">
        {loading ? t('loading') : error ? error : data ? (data.total ? t('journalsFound', { n: formatNumber(data.total)! }) : t('noJournals')) : ''}
      </p>

      {!data && !loading && !error && (
        <div className="mt-4">
          <EmptyState icon="library" title="Search the journal rankings">
            Enter a journal name, an ISSN or a subject, or choose a subject area and quartile to browse the highest-ranked journals.
          </EmptyState>
        </div>
      )}

      {loading && !data && (
        <ul className="mt-4 grid gap-3" aria-hidden="true">
          {Array.from({ length: 4 }, (_, i) => <li key={i} className="card space-y-3 p-5"><div className="skeleton h-5 w-2/3" /><div className="skeleton h-4 w-1/3" /><div className="skeleton h-3 w-1/2" /></li>)}
        </ul>
      )}

      {data && (
        <AnimatePresence mode="wait">
          <m.ul key={`${page}-${data.total}`} variants={list} initial="hidden" animate="show" exit={{ opacity: 0 }}
            className={`mt-4 grid gap-3 transition-opacity ${loading ? 'opacity-60' : ''}`}>
            {data.results.map(j => (
              <m.li key={j.id} variants={item}>
                <GlowCard innerClassName="p-5">
                <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
                  <div className="min-w-0">
                    <h2 className="text-xl font-semibold leading-snug">{j.title}</h2>
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                      <QuartilePill quartile={j.quartile} />
                      {j.open_access && <span className="pill bg-success-soft text-success"><Icon name="unlock" className="h-3.5 w-3.5" />{t('openAccess')}</span>}
                      {j.sjr_score ? <span className="text-muted">SJR <strong className="text-fg">{j.sjr_score}</strong></span> : null}
                      {j.h_index ? <span className="text-muted">h-index <strong className="text-fg">{j.h_index}</strong></span> : null}
                    </div>
                    <p className="hint mt-2">{[j.publisher, j.country, j.issn.length ? `ISSN ${j.issn.join(', ')}` : null].filter(Boolean).join(' · ')}</p>
                    {j.categories.length > 0 && <p className="mt-1 text-sm">{j.categories.slice(0, 3).join('; ')}</p>}
                  </div>
                  <CompareToggle journal={j} />
                </div>
                </GlowCard>
              </m.li>
            ))}
          </m.ul>
        </AnimatePresence>
      )}

      {data && pages > 1 && (
        <nav className="mt-8 flex items-center justify-between gap-4" aria-label="Search results pages">
          <Button disabled={page <= 1 || loading} onClick={() => search(page - 1)}>Previous</Button>
          <span className="text-sm text-muted">{t('pageOf', { page, pages })}</span>
          <Button disabled={page >= pages || loading} onClick={() => search(page + 1)}>Next</Button>
        </nav>
      )}
    </div>
  );
}
