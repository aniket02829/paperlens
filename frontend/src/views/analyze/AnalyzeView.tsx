import { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, m } from 'motion/react';
import { api } from '../../lib/api';
import { storage } from '../../lib/storage';
import { t } from '../../lib/strings';
import { Icon } from '../../components/Icon';
import { NumberTicker } from '../../components/magic/NumberTicker';
import { GridPattern } from '../../components/magic/GridPattern';
import { useToast } from '../../components/Toast';
import type { BulkResponse, HistoryEntry, PaperResult } from '../../types';
import { InputCard, type InputMode } from './InputCard';
import { ResultCard } from './ResultCard';
import { ResultSkeleton } from './ResultSkeleton';
import { BulkResult } from './BulkResult';
import { History } from './History';
import { Landing } from './Landing';
import { rerunQuery } from './verdict';

const HISTORY_KEY = 'paperlens_history';

type Status =
  | { kind: 'idle' }
  | { kind: 'loading'; steps: string[] }
  | { kind: 'single'; result: PaperResult; query: string | null }
  | { kind: 'bulk'; data: BulkResponse };

function setQueryParam(query: string | null) {
  const url = new URL(location.href);
  if (query) url.searchParams.set('q', query); else url.searchParams.delete('q');
  history.replaceState(null, '', url.pathname + url.search + location.hash);
}

export function AnalyzeView() {
  const [mode, setMode] = useState<InputMode>('search');
  const [query, setQuery] = useState(() => new URLSearchParams(location.search).get('q') || '');
  const [status, setStatus] = useState<Status>({ kind: 'idle' });
  const [error, setError] = useState<string | null>(null);
  const [historyItems, setHistoryItems] = useState<HistoryEntry[]>(() => storage.get<HistoryEntry[]>(HISTORY_KEY, []));
  const [stats, setStats] = useState({ journals: 32193, conferences: 987 });
  const inputRef = useRef<HTMLDivElement>(null);
  const toast = useToast();

  useEffect(() => {
    fetch('/stats').then(r => r.json()).then(s => setStats({ journals: s.journals, conferences: s.conferences })).catch(() => {});
  }, []);

  const remember = useCallback((results: PaperResult[], query: string | null) => {
    setHistoryItems(current => {
      let items = current;
      for (const result of results) {
        if (result.category === 'error') continue;
        const rerun = rerunQuery(result, query);
        const entry: HistoryEntry = {
          title: result.title, category: result.category, venue: result.venue,
          rank: result.category === 'journal' ? result.quartile : result.core_rank, query: rerun, at: Date.now(),
        };
        items = [entry, ...items.filter(i => !(rerun && i.query === rerun) && i.title !== entry.title)].slice(0, 10);
      }
      storage.set(HISTORY_KEY, items);
      return items;
    });
  }, []);

  const runLookup = useCallback(async (value: string) => {
    setError(null);
    setStatus({ kind: 'loading', steps: [t('stepSearching'), t('stepDatabases'), t('stepRanking')] });
    try {
      const data = await api<{ result: PaperResult }>('/api/lookup', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ query: value }),
      });
      setQueryParam(value);
      setStatus({ kind: 'single', result: data.result, query: value });
      remember([data.result], value);
    } catch (err) {
      setStatus({ kind: 'idle' });
      setError((err as Error).message);
    }
  }, [remember]);

  const runFiles = useCallback(async (files: File[], bulk: boolean) => {
    setError(null);
    const form = new FormData();
    if (bulk) files.forEach(f => form.append('files', f)); else form.append('file', files[0]);
    setStatus({ kind: 'loading', steps: bulk
      ? [t('stepUploadingMany', { n: files.length }), t('stepReading'), t('stepDatabases'), t('stepRanking')]
      : [t('stepUploading'), t('stepReading'), t('stepDatabases'), t('stepRanking')] });
    try {
      if (bulk) {
        const data = await api<BulkResponse>('/analyze-bulk', { method: 'POST', body: form }, 180000);
        setStatus({ kind: 'bulk', data });
        remember(data.results, null);
      } else {
        const data = await api<{ result: PaperResult }>('/analyze', { method: 'POST', body: form });
        if (data.result.category === 'error') {
          setStatus({ kind: 'idle' });
          setError(data.result.error);
        } else {
          setStatus({ kind: 'single', result: data.result, query: null });
          remember([data.result], null);
        }
      }
    } catch (err) {
      setStatus({ kind: 'idle' });
      setError((err as Error).message);
    }
  }, [remember]);

  // A shared link (?q=...) runs its lookup on arrival, once.
  const ranShared = useRef(false);
  useEffect(() => {
    const shared = new URLSearchParams(location.search).get('q');
    if (shared && !ranShared.current) {
      ranShared.current = true;
      runLookup(shared);
    }
  }, [runLookup]);

  const reset = () => {
    setStatus({ kind: 'idle' });
    setError(null);
    setQueryParam(null);
    inputRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    (inputRef.current?.querySelector<HTMLElement>(mode === 'search' ? '#queryInput' : '[role="tab"][aria-selected="true"]'))?.focus({ preventScroll: true });
  };

  const busy = status.kind === 'loading';

  return (
    <>
      {/* Hero */}
      <section className="relative overflow-hidden border-b border-border bg-surface" aria-labelledby="analyzeHeading">
        <GridPattern className="[mask-image:radial-gradient(ellipse_at_top_left,black_10%,transparent_65%)] opacity-70" />
        <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/50 to-transparent" aria-hidden="true" />
        <div className="container-page relative grid grid-cols-1 gap-10 pb-16 pt-12 sm:pt-16 lg:grid-cols-12 lg:items-center lg:gap-12 lg:pb-20 lg:pt-20">
          <m.div className="min-w-0 lg:col-span-5"
            initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}>
            <p className="eyebrow">Research paper classification</p>
            <h1 id="analyzeHeading" className="mt-4 text-display-md font-semibold sm:text-display-lg">
              Identify the publication venue and ranking of any research paper
            </h1>
            <p className="mt-5 text-lg leading-relaxed text-muted">
              PaperLens determines whether a paper is a journal article, a conference paper or a preprint, and reports the venue’s Scimago quartile or CORE conference ranking.
            </p>
            <dl className="mt-8 grid grid-cols-3 divide-x divide-border border-y border-border">
              {[
                { label: 'Journals indexed', value: <NumberTicker value={stats.journals} /> },
                { label: 'Conferences ranked', value: <NumberTicker value={stats.conferences} /> },
                { label: 'Records searchable', value: '250M+' },
              ].map(s => (
                <div key={s.label} className="px-3 py-4 first:pl-0">
                  <dt className="text-xs font-bold text-muted">{s.label}</dt>
                  <dd className="mt-1 font-serif text-2xl font-semibold tabular-nums text-fg">{s.value}</dd>
                </div>
              ))}
            </dl>
          </m.div>
          <m.div ref={inputRef} className="min-w-0 lg:col-span-7"
            initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}>
            <InputCard mode={mode} onModeChange={setMode} query={query} onQueryChange={setQuery} busy={busy}
              onLookup={runLookup} onAnalyzeFiles={runFiles} onError={setError} />
            <AnimatePresence>
              {error && (
                <m.div initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
                  className="mt-4 flex gap-3 rounded-md border border-danger/40 bg-danger-soft p-4 text-danger" role="alert">
                  <Icon name="alert" className="mt-0.5 h-5 w-5" />
                  <div>
                    <p className="font-bold">The paper could not be classified</p>
                    <p className="mt-1 text-sm text-fg">{error}</p>
                  </div>
                </m.div>
              )}
            </AnimatePresence>
          </m.div>
        </div>
      </section>

      {/* Result */}
      <div className="container-page max-w-4xl">
        <div className="mt-10 empty:mt-0">
          <AnimatePresence mode="wait">
            {status.kind === 'loading' && <ResultSkeleton key="loading" steps={status.steps} />}
            {status.kind === 'single' && <ResultCard key="single" result={status.result} query={status.query} onReset={reset} />}
            {status.kind === 'bulk' && <BulkResult key="bulk" data={status.data} onReset={reset} />}
          </AnimatePresence>
        </div>
        {historyItems.length > 0 && (
          <div className="mt-10">
            <History items={historyItems}
              onRerun={q => { setMode('search'); setQuery(q); runLookup(q); }}
              onClear={() => { storage.remove(HISTORY_KEY); setHistoryItems([]); toast(t('historyCleared')); }} />
          </div>
        )}
      </div>

      <Landing />
    </>
  );
}
