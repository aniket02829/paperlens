import { useEffect, useState, type ReactNode } from 'react';
import { GlowCard } from '../components/GlowCard';
import { m } from 'motion/react';
import { api } from '../lib/api';
import { t } from '../lib/strings';
import { Icon } from '../components/Icon';
import { EmptyState, ExternalLink, QuartilePill } from '../components/ui';
import { useCompare, MAX_COMPARE } from '../state/compare';
import type { Journal } from '../types';

export function CompareView() {
  const { ids, toggle } = useCompare();
  const [journals, setJournals] = useState<Journal[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ids.length) { setJournals([]); return; }
    setLoading(true);
    setError(null);
    api<{ results: Journal[] }>(`/api/journals?ids=${ids.join(',')}`)
      .then(r => setJournals(r.results))
      .catch(err => setError((err as Error).message))
      .finally(() => setLoading(false));
  }, [ids]);

  const best = Math.max(0, ...journals.map(j => j.sjr_score || 0));
  const rows: [string, (j: Journal) => ReactNode][] = [
    [t('colQuartile'), j => <QuartilePill quartile={j.quartile} />],
    ['SJR', j => <span className="font-serif text-lg font-semibold">{j.sjr_score ?? '–'}</span>],
    ['h-index', j => j.h_index ?? '–'],
    [t('factPublisher'), j => j.publisher || '–'],
    [t('country'), j => j.country || '–'],
    [t('openAccess'), j => (j.open_access ? t('yes') : t('no'))],
    ['ISSN', j => j.issn.join(', ') || '–'],
    [t('factSubjects'), j => <ul className="space-y-1">{j.categories.slice(0, 6).map(c => <li key={c}>{c}</li>)}</ul>],
    [t('moreInfo'), j => <ExternalLink href={`https://www.scimagojr.com/journalsearch.php?q=${encodeURIComponent(j.issn[0] || j.title)}`}>Scimago</ExternalLink>],
  ];

  return (
    <div className="container-page py-12">
      <p className="eyebrow">Side by side</p>
      <h1 className="mt-2 text-display-sm font-semibold sm:text-display-md">Compare journals</h1>
      <p className="mt-3 max-w-2xl text-muted">Compare up to {MAX_COMPARE} journals side by side. Journals can be added from Journal search or from the recommendations for a preprint.</p>

      <div className="mt-8">
        {!ids.length ? (
          <EmptyState icon="scale" title="No journals have been selected">
            <p>Add journals from Journal search to compare their quartile, SJR score, h-index and publisher.</p>
            <a href="#/journals" className="btn-primary mt-5">Search journals</a>
          </EmptyState>
        ) : error ? (
          <p className="card p-6 text-danger" role="alert">{error}</p>
        ) : loading && !journals.length ? (
          <div className="card space-y-4 p-6" aria-busy="true"><p role="status">{t('loading')}</p>
            {Array.from({ length: 5 }, (_, i) => <div key={i} className="skeleton h-5 w-full" aria-hidden="true" />)}</div>
        ) : (
          <m.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
            <GlowCard innerClassName="overflow-x-auto">
            <table className="table-base">
              <caption className="sr-only">Comparison of selected journals</caption>
              <thead className="sticky top-0">
                <tr>
                  <th scope="col" className="w-36"><span className="sr-only">{t('colMeasure')}</span></th>
                  {journals.map(j => (
                    <th key={j.id} scope="col" className="min-w-[13rem] align-top">
                      <span className="block font-serif text-lg font-semibold leading-snug">{j.title}</span>
                      {j.sjr_score && j.sjr_score === best && journals.length > 1 && <span className="pill mt-2 bg-q1-soft text-q1">{t('highestSjr')}</span>}
                      <button type="button" onClick={() => toggle(j.id)} className="btn-ghost mt-1 min-h-[36px] px-2 text-xs font-bold">
                        <Icon name="x" />{t('remove')}<span className="sr-only">: {j.title}</span>
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map(([label, render]) => (
                  <tr key={label}>
                    <th scope="row" className="bg-surface text-muted">{label}</th>
                    {journals.map(j => <td key={j.id}>{render(j)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
            </GlowCard>
          </m.div>
        )}
      </div>
    </div>
  );
}
