import { useEffect, useRef, type ReactNode } from 'react';
import { GlowCard } from '../../components/GlowCard';
import { m } from 'motion/react';
import { cn } from '../../lib/cn';
import { formatNumber, percent } from '../../lib/format';
import { toBibtex } from '../../lib/bibtex';
import { t } from '../../lib/strings';
import { Icon } from '../../components/Icon';
import { Alert, Button, CategoryBadge, ExternalLink, QuartilePill, CATEGORY_STYLE } from '../../components/ui';
import { ConfidenceRing } from '../../components/ConfidenceRing';
import { useCopy } from '../../components/Toast';
import { useCompare } from '../../state/compare';
import type { PaperResult } from '../../types';
import { rerunQuery, verdict } from './verdict';

const ACCENT_BAR: Record<string, string> = {
  journal: 'before:bg-journal', conference: 'before:bg-conference', arxiv: 'before:bg-preprint',
  unknown: 'before:bg-border-strong', error: 'before:bg-danger',
};

const list = { hidden: {}, show: { transition: { staggerChildren: 0.04, delayChildren: 0.1 } } };
const item = { hidden: { opacity: 0, y: 6 }, show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: [0.22, 1, 0.36, 1] as const } } };

function Fact({ label, children }: { label: string; children: ReactNode }) {
  if (children === null || children === undefined || children === '' || children === false) return null;
  return (
    <m.div variants={item}>
      <dt className="text-xs font-bold uppercase tracking-wider text-muted">{label}</dt>
      <dd className="mt-1 break-words text-sm text-fg">{children}</dd>
    </m.div>
  );
}

function doiLink(doi: string | null) {
  return doi ? <ExternalLink href={`https://doi.org/${doi}`}>{doi}</ExternalLink> : null;
}

export function summaryText(result: PaperResult) {
  const v = verdict(result);
  return [
    result.title,
    `${t('summaryVerdict')}: ${v.headline}`,
    result.venue ? `${t('factVenue')}: ${result.venue}` : null,
    result.doi ? `DOI: https://doi.org/${result.doi}` : null,
    `${t('summaryConfidence')}: ${percent(result.confidence)}%`,
    `PaperLens (${location.origin})`,
  ].filter(Boolean).join('\n');
}

function shareLink(query: string) {
  const url = new URL(location.origin + location.pathname);
  url.searchParams.set('q', query);
  return url.href;
}

export function ResultCard({ result, query, onReset }: { result: PaperResult; query: string | null; onReset: () => void }) {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const copy = useCopy();
  const v = verdict(result);
  const share = rerunQuery(result, query);

  useEffect(() => {
    headingRef.current?.focus({ preventScroll: true });
    headingRef.current?.closest('article')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, [result]);

  let rank: ReactNode = null;
  if (result.category === 'journal' && /^Q[1-4]$/.test(result.quartile || '')) {
    rank = (
      <span className="flex flex-wrap items-center gap-2">
        <QuartilePill quartile={result.quartile} />
        {result.sjr_score ? <span>SJR {result.sjr_score}</span> : null}
        {result.h_index ? <span className="text-muted">· h-index {result.h_index}</span> : null}
      </span>
    );
  } else if (result.category === 'conference' && result.core_rank) {
    rank = `CORE ${result.core_rank}${result.core_acronym ? ` (${result.core_acronym})` : ''}`;
  }

  const byline = [result.authors, result.year].filter(Boolean).join(' · ');
  const venueLabel = result.category === 'conference' ? t('factConference') : result.category === 'arxiv' ? t('factRepository') : t('factVenue');

  return (
    <m.article initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      className="scroll-mt-24" aria-labelledby="resTitle">
      <GlowCard>
      {/* Verdict */}
      <div className={cn('relative border-b border-border p-5 before:absolute before:inset-y-0 before:left-0 before:w-1 sm:p-8', ACCENT_BAR[result.category])}>
        <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-start">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <CategoryBadge category={result.category} />
              {result.is_arxiv && result.category !== 'arxiv' && <span className={cn('pill', CATEGORY_STYLE.arxiv.cls)}>{t('alsoOnArxiv')}</span>}
              {result.filename && <span className="text-xs text-muted">{result.filename}</span>}
            </div>
            <h2 id="resTitle" ref={headingRef} tabIndex={-1} className="mt-3 text-display-sm font-semibold focus:outline-none">{v.headline}</h2>
            <p className="mt-2 max-w-prose text-muted">{v.detail}</p>
          </div>
          <ConfidenceRing confidence={result.confidence} />
        </div>
      </div>

      <Warnings result={result} />

      <div className="p-5 sm:p-8">
        {/* Paper */}
        <p className="eyebrow">Paper</p>
        <h3 className="mt-1 text-xl font-semibold leading-snug sm:text-2xl">{result.title || t('unknownTitle')}</h3>
        {byline && <p className="mt-1 line-clamp-2 text-sm text-muted">{byline}</p>}

        <m.dl variants={list} initial="hidden" animate="show" className="mt-6 grid gap-x-8 gap-y-5 border-t border-border pt-6 sm:grid-cols-2 lg:grid-cols-3">
          <Fact label={venueLabel}>{result.venue}</Fact>
          <Fact label={t('factRank')}>{rank}</Fact>
          <Fact label={t('factConfType')}>{result.conference_type ? t(`confType_${result.conference_type}`) : null}</Fact>
          <Fact label={t('factPublisher')}>{result.publisher}</Fact>
          <Fact label={t('factYear')}>{result.year}</Fact>
          <Fact label={t('factCitations')}>{formatNumber(result.citation_count)}</Fact>
          <Fact label="DOI">{doiLink(result.published_doi ? null : result.doi)}</Fact>
          <Fact label={t('factPublishedVersion')}>{doiLink(result.published_doi)}</Fact>
          <Fact label="arXiv">{result.arxiv_id ? <ExternalLink href={`https://arxiv.org/abs/${result.arxiv_id}`}>{result.arxiv_id}</ExternalLink> : null}</Fact>
          <Fact label={t('factFreeCopy')}>{result.oa_url ? <ExternalLink href={result.oa_url}>{t('readFree')}</ExternalLink> : null}</Fact>
          <Fact label={t('factSubjects')}>{result.categories || result.topics.join('; ') || result.fields_of_study}</Fact>
          <Fact label={t('factFees')}>{result.doaj?.apc === 'No' ? t('feesNone') : result.doaj?.apc_amount || null}</Fact>
          <Fact label={t('factPages')}>{result.page_count || null}</Fact>
        </m.dl>

        <VenueImpact stats={result.venue_stats} />

        <TrustChecks result={result} />
        <Suggestions result={result} />

        <div className="mt-8 space-y-3">
          <details className="group rounded-md border border-border">
            <summary className="flex min-h-[44px] cursor-pointer list-none items-center justify-between px-4 font-bold">
              {t('whyTitle')}<Icon name="arrowRight" className="h-4 w-4 transition-transform group-open:rotate-90" />
            </summary>
            <ul className="space-y-2 px-4 pb-4 text-sm">
              {result.signals.map((signal, i) => (
                <li key={i} className="flex items-start gap-2"><Icon name="check" className="mt-0.5 h-4 w-4 text-muted" /><span>{signal}</span></li>
              ))}
            </ul>
          </details>
          {result.abstract && (
            <details className="group rounded-md border border-border">
              <summary className="flex min-h-[44px] cursor-pointer list-none items-center justify-between px-4 font-bold">
                {t('abstractTitle')}<Icon name="arrowRight" className="h-4 w-4 transition-transform group-open:rotate-90" />
              </summary>
              <p className="px-4 pb-4 text-sm leading-relaxed">{result.abstract}</p>
            </details>
          )}
        </div>

        <div className="no-print mt-8 flex flex-wrap gap-2 border-t border-border pt-6">
          <Button icon="copy" onClick={() => copy(summaryText(result))}>{t('copySummary')}</Button>
          {result.category !== 'unknown' && <Button icon="quote" onClick={() => copy(toBibtex(result))}>{t('copyBibtex')}</Button>}
          {share && <Button icon="link" onClick={() => copy(shareLink(share))}>{t('copyLink')}</Button>}
          <Button icon="printer" onClick={() => window.print()}>{t('printReport')}</Button>
          <Button variant="primary" icon="reset" className="sm:ml-auto" onClick={onReset}>{t('checkAnother')}</Button>
        </div>
      </div>
      </GlowCard>
    </m.article>
  );
}

/** Alerts that must be seen before the facts: retraction, hijacking, predatory lists, Scopus discontinuation. */
function Warnings({ result }: { result: PaperResult }) {
  const warnings = result.trust?.warnings || [];
  const hijacked = result.watchlist?.hijacked;
  const predatory = result.watchlist?.predatory_journal;
  const predatoryPublisher = result.watchlist?.predatory_publisher;
  const scopus = result.scopus;
  const alerts: ReactNode[] = [];

  if (result.is_retracted) alerts.push(<Alert key="retracted" tone="danger" title={t('retractedTitle')}>{t('retractedText')}</Alert>);
  if (hijacked) {
    alerts.push(
      <Alert key="hijacked" tone="danger" title={t('hijackedTitle')} role="alert">
        {hijacked.authentic_url
          ? <>{t('hijackedText', { name: hijacked.authentic_name })}<ExternalLink href={hijacked.authentic_url}>{hijacked.authentic_url.replace(/^https?:\/\//, '')}</ExternalLink></>
          : t('hijackedNoUrl', { name: hijacked.authentic_name })}
      </Alert>,
    );
  }
  if (predatory) alerts.push(<Alert key="predatory" tone="danger" title={t('predatoryTitle')}>{t('predatoryText', { name: predatory.name })}</Alert>);
  if (predatoryPublisher && !predatory) alerts.push(<Alert key="publisher" tone="warning" title={t('predatoryPublisherTitle')}>{t('predatoryPublisherText', { name: predatoryPublisher.name })}</Alert>);
  if (scopus?.discontinued) {
    const year = scopus.discontinued_year ? ` in ${scopus.discontinued_year}` : '';
    const reason = scopus.discontinued_reason === 'Journal change policy' ? t('reasonPolicy') : t('reasonDiscontinuation');
    alerts.push(<Alert key="discontinued" tone="warning" title={t('discontinuedTitle')}>{t('discontinuedText', { year, reason })}</Alert>);
  }
  if (warnings.includes('not_in_sjr_or_doaj') && !predatory && !scopus?.discontinued) {
    alerts.push(<Alert key="unindexed" tone="warning" title={t('notIndexedTitle')}>{t('notIndexedText')}</Alert>);
  }
  if (!alerts.length) return null;
  return <div className="space-y-3 px-5 pt-6 sm:px-8">{alerts}</div>;
}

/** OpenAlex citation statistics for a venue that no ranking covers; clearly labelled as an estimate. */
function VenueImpact({ stats }: { stats: PaperResult['venue_stats'] }) {
  if (!stats || (stats.h_index === undefined && stats.mean_citedness_2yr === undefined)) return null;
  const figures = [
    stats.h_index !== undefined ? t('impactHIndex', { h: stats.h_index }) : null,
    stats.mean_citedness_2yr !== undefined ? t('impactCitedness', { n: stats.mean_citedness_2yr }) : null,
    stats.works_count ? t('impactWorks', { n: formatNumber(stats.works_count)! }) : null,
  ].filter(Boolean) as string[];
  return (
    <section className="mt-6 rounded-md border border-dashed border-border-strong p-4" aria-labelledby="impactHeading">
      <h3 id="impactHeading" className="flex items-center gap-2 font-sans text-sm font-bold uppercase tracking-wider text-muted">
        <Icon name="info" className="h-4 w-4" />{t('factImpact')}
      </h3>
      <ul className="mt-2 flex flex-wrap gap-x-6 gap-y-1 font-serif text-lg font-semibold tabular-nums">
        {figures.map(f => <li key={f}>{f}</li>)}
      </ul>
      <p className="hint mt-2">{t('impactHint')}</p>
    </section>
  );
}

function TrustChecks({ result }: { result: PaperResult }) {
  const trust = result.trust;
  if (!trust) return null;
  const items: { tone: 'good' | 'warn' | 'info'; text: string }[] = [];
  if (result.category === 'journal') {
    items.push(trust.indexed_in_sjr ? { tone: 'good', text: t('trustInSjr') } : { tone: 'warn', text: t('trustNotInSjr') });
    if (result.scopus?.discontinued) items.push({ tone: 'warn', text: t('trustScopusDiscontinued', { year: result.scopus.discontinued_year ? ` in ${result.scopus.discontinued_year}` : '' }) });
    else if (trust.indexed_in_scopus === true) items.push({ tone: 'good', text: t('trustInScopus') });
    else if (trust.indexed_in_scopus === false) items.push({ tone: 'warn', text: t('trustNotInScopus') });
  }
  if (result.category === 'conference') items.push(trust.in_core ? { tone: 'good', text: t('trustInCore') } : { tone: 'info', text: t('trustNotInCore') });
  if (trust.in_doaj === true) items.push({ tone: 'good', text: t('trustInDoaj') });
  if (result.category === 'journal' && trust.in_doaj === false && !trust.indexed_in_sjr && !trust.indexed_in_scopus) items.push({ tone: 'warn', text: t('trustNotInDoaj') });
  if (result.doaj?.apc === 'No') items.push({ tone: 'good', text: t('trustDoajNoFees') });
  else if (result.doaj?.apc_amount) items.push({ tone: 'info', text: t('trustDoajFees', { amount: result.doaj.apc_amount }) });
  if (result.doaj?.review_process) items.push({ tone: 'info', text: t('trustDoajReview', { process: result.doaj.review_process.toLowerCase() }) });
  if (!result.is_retracted && result.matched_by) items.push({ tone: 'good', text: t('trustNotRetracted') });
  if (result.watchlist && !result.watchlist.hijacked && !result.watchlist.predatory_journal && !result.watchlist.predatory_publisher && result.category !== 'arxiv') {
    items.push({ tone: 'good', text: t('trustNoWatchlist') });
  }
  if (result.is_open_access === true) items.push({ tone: 'good', text: t('trustOpenAccess') });
  if (!items.length) return null;
  const icon = { good: 'check', warn: 'alert', info: 'info' } as const;
  const color = { good: 'text-success', warn: 'text-warning', info: 'text-muted' };
  return (
    <section className="mt-8 rounded-md bg-surface-2 p-4 sm:p-5" aria-labelledby="trustHeading">
      <h3 id="trustHeading" className="flex items-center gap-2 font-sans text-base font-bold"><Icon name="shield" className="h-5 w-5 text-primary-text" />{t('trustTitle')}</h3>
      <ul className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
        {items.map(i => <li key={i.text} className="flex items-start gap-2"><Icon name={icon[i.tone]} className={cn('mt-0.5 h-4 w-4', color[i.tone])} /><span>{i.text}</span></li>)}
      </ul>
    </section>
  );
}

function Suggestions({ result }: { result: PaperResult }) {
  const { has, toggle } = useCompare();
  if (!result.suggested_journals.length) return null;
  const title = t('suggestTitle', { field: result.suggestion_field || '' });
  return (
    <section className="mt-8" aria-labelledby="suggestHeading">
      <h3 id="suggestHeading" className="text-xl font-semibold">{title}</h3>
      <p className="hint mt-1">{t('suggestHint')}</p>
      <div className="mt-4 overflow-x-auto rounded-md border border-border">
        <table className="table-base">
          <caption className="sr-only">{title}</caption>
          <thead><tr>
            <th scope="col">{t('colJournal')}</th><th scope="col">{t('colQuartile')}</th><th scope="col">SJR</th>
            <th scope="col"><span className="sr-only">{t('colActions')}</span></th>
          </tr></thead>
          <tbody className="divide-y divide-border">
            {result.suggested_journals.map(j => (
              <tr key={j.name}>
                <td className="font-bold">{j.name}{j.open_access && <span className="block text-xs font-normal text-success">{t('openAccess')}</span>}</td>
                <td><QuartilePill quartile={j.quartile} /></td>
                <td>{j.sjr_score ?? '–'}</td>
                <td>{j.id !== null && (
                  <button type="button" aria-pressed={has(j.id)} onClick={() => toggle(j.id!)} className="btn-ghost min-h-[36px] px-2 text-xs">
                    <Icon name={has(j.id) ? 'check' : 'plus'} />{has(j.id) ? t('inCompare') : t('addCompare')}<span className="sr-only">: {j.name}</span>
                  </button>
                )}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
