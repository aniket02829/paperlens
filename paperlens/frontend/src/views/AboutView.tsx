import { useEffect, useState } from 'react';
import { BlurFade } from '../components/magic/BlurFade';
import { formatNumber } from '../lib/format';
import { t } from '../lib/strings';

interface Stats {
  journals?: number; conferences?: number; scopus_sources?: number; doaj_journals?: number;
  hijacked_journals?: number; predatory_entries?: number; editions?: Record<string, string>;
}

const GLOSSARY = [
  ['Journal quartile (Q1–Q4)', 'Scimago ranks the journals in each subject category by citation impact. Q1 comprises the top 25%, Q2 the next 25%, and so on to Q4. The journal’s best quartile across its categories is reported.'],
  ['SJR score', 'A measure of the citations received by a journal’s papers, weighted by the prestige of the citing journals. Scores should be compared only within the same field.'],
  ['h-index', 'The journal has h papers that have each been cited at least h times.'],
  ['Conference type', 'IEEE denotes a conference organised or published by the IEEE. National denotes a national or regional event. All other conferences are reported as International.'],
  ['CORE conference rank (A*, A, B, C)', 'The CORE ranking of computing conferences. A* denotes flagship conferences (approximately the top 7%), A excellent, B good, and C conferences meeting minimum standards.'],
  ['Preprint', 'A paper made public, for example on arXiv, before or without peer review. It may subsequently be published in a journal or at a conference.'],
  ['Scopus source list', 'Elsevier’s list of every journal Scopus indexes, including journals it has discontinued for publication concerns. A journal may still hold a Scimago quartile from an earlier edition after Scopus has dropped it.'],
  ['DOAJ', 'The Directory of Open Access Journals lists open-access journals that meet defined quality standards, with their fees and review process. Journals indexed in neither Scopus (SJR) nor DOAJ warrant careful verification before submission.'],
  ['Hijacked journal', 'A fraudulent website that imitates a legitimate journal, usually to collect fees. PaperLens checks the Retraction Watch Hijacked Journal Checker and shows the authentic publisher’s address.'],
  ['Predatory list', 'Stop Predatory Journals is a community-maintained list of journals and publishers with questionable practices. A match is a reason to verify, not a verdict: a legitimate journal may share a name.'],
  ['Citation impact (OpenAlex)', 'When a venue has no Scimago or CORE rank, PaperLens shows the h-index and citations per paper computed by OpenAlex. These are estimates derived from open citation data, not an official ranking.'],
  ['Confidence', 'The degree to which the evidence agrees. High confidence indicates that several independent databases agree; low confidence indicates that the result relies on textual evidence alone.'],
];

const SOURCES = [
  ['Scimago Journal Rank (SJR)', 'https://www.scimagojr.com/journalrank.php', 'journal quartiles, SJR scores and h-index'],
  ['CORE', 'https://portal.core.edu.au/conf-ranks/', 'conference rankings'],
  ['Scopus source list', 'https://www.elsevier.com/products/scopus/content', 'journals indexed in Scopus, with discontinued titles'],
  ['DOAJ', 'https://doaj.org', 'open-access journals, their fees and review process'],
  ['Retraction Watch Hijacked Journal Checker', 'https://retractionwatch.com/the-retraction-watch-hijacked-journal-checker/', 'hijacked journal websites'],
  ['Stop Predatory Journals', 'https://predatoryjournals.org', 'community list of predatory journals and publishers'],
  ['CrossRef', 'https://www.crossref.org', 'registered DOI metadata'],
  ['OpenAlex', 'https://openalex.org', 'more than 250 million scholarly works, open-access and retraction status, venue citation statistics'],
  ['Semantic Scholar', 'https://www.semanticscholar.org', 'citations, abstracts and published versions of preprints'],
  ['arXiv', 'https://arxiv.org', 'preprint records and subject classes'],
];

function editionRows(stats: Stats): [string, string][] {
  const e = stats.editions || {};
  const rows: [string, string][] = [];
  if (e.sjr_edition) rows.push(['Scimago Journal Rank', `${e.sjr_edition} edition · ${formatNumber(stats.journals)} sources`]);
  if (e.core_edition) rows.push(['CORE conference ranking', `${e.core_edition} · ${formatNumber(stats.conferences)} conferences`]);
  if (e.scopus_list) rows.push(['Scopus source list', `${e.scopus_list} · ${formatNumber(stats.scopus_sources)} sources`]);
  if (e.doaj_downloaded) rows.push(['DOAJ', `${e.doaj_downloaded} · ${formatNumber(stats.doaj_journals)} journals`]);
  if (e.hijacked_updated) rows.push(['Hijacked Journal Checker', `${e.hijacked_updated} · ${formatNumber(stats.hijacked_journals)} journals`]);
  if (stats.predatory_entries) rows.push(['Stop Predatory Journals', `${formatNumber(stats.predatory_entries)} journals and publishers`]);
  return rows;
}

const LIMITS = [
  'Rankings indicate the standing of a venue, not the quality of an individual paper.',
  'Scanned documents (images of pages) cannot be read. Such papers should be searched by DOI or title.',
  'CORE ranks computing conferences only; conferences in other fields are generally reported as unranked.',
  'A journal that is not indexed is not necessarily predatory, but it should be verified with care.',
];

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <BlurFade as="section" className="border-t border-border pt-10">
      <h2 id={id} className="text-2xl font-semibold">{title}</h2>
      <div className="mt-4 text-fg">{children}</div>
    </BlurFade>
  );
}

export function AboutView() {
  const [stats, setStats] = useState<Stats>({});
  useEffect(() => {
    fetch('/stats').then(r => r.json()).then(setStats).catch(() => {});
  }, []);
  const editions = editionRows(stats);
  return (
    <div className="container-page max-w-3xl space-y-12 py-12">
      <div>
        <p className="eyebrow">About</p>
        <h1 className="mt-2 text-display-sm font-semibold sm:text-display-md">About PaperLens</h1>
        <p className="mt-4 text-lg leading-relaxed text-muted">PaperLens assists students, researchers and reviewers in establishing where a paper was published and how the venue is ranked. The service is free of charge and requires no account.</p>
      </div>

      <Section id="glossary" title="Interpreting the results">
        <dl className="divide-y divide-border rounded-lg border border-border bg-surface">
          {GLOSSARY.map(([term, def]) => (
            <div key={term} className="grid gap-1 p-4 sm:grid-cols-[14rem_1fr] sm:gap-6">
              <dt className="font-bold">{term}</dt><dd className="text-sm text-muted">{def}</dd>
            </div>
          ))}
        </dl>
      </Section>

      <Section id="sources" title="Data sources">
        <ul className="space-y-2">
          {SOURCES.map(([name, url, what]) => <li key={name}><a href={url} rel="noopener">{name}</a><span className="text-muted">: {what}</span></li>)}
        </ul>
        {editions.length > 0 && (
          <>
            <h3 className="mt-8 font-sans text-base font-bold">{t('dataEditions')}</h3>
            <dl className="mt-3 divide-y divide-border rounded-lg border border-border bg-surface text-sm">
              {editions.map(([name, value]) => (
                <div key={name} className="grid gap-1 p-3 sm:grid-cols-[14rem_1fr] sm:gap-6">
                  <dt className="font-bold">{name}</dt><dd className="text-muted">{value}</dd>
                </div>
              ))}
            </dl>
          </>
        )}
      </Section>

      <Section id="limitations" title="Limitations">
        <ul className="list-disc space-y-2 pl-6">{LIMITS.map(l => <li key={l}>{l}</li>)}</ul>
      </Section>

      <Section id="privacy" title="Privacy">
        <p>Uploaded documents are deleted as soon as they have been analyzed. PaperLens uses no accounts, cookies or trackers. Recent classifications are stored only in the user’s own browser and can be cleared at any time.</p>
      </Section>

      <Section id="accessibility" title="Accessibility">
        <p>PaperLens is designed to meet WCAG 2.2 level AA. It supports keyboard navigation, screen readers, dark mode, enlarged text and reduced motion. Accessibility issues may be reported on GitHub.</p>
      </Section>

      <Section id="api" title="API">
        <p>PaperLens provides a free JSON API, subject to fair-use rate limits.</p>
        <pre tabIndex={0} aria-label="API examples" className="card mt-4 overflow-x-auto p-4 font-mono text-sm"><code>{`curl -X POST https://paperlens-imv4.onrender.com/api/lookup \\
  -H 'Content-Type: application/json' -d '{"query": "10.1109/CVPR.2016.90"}'

curl -F file=@paper.pdf https://paperlens-imv4.onrender.com/analyze
curl 'https://paperlens-imv4.onrender.com/api/journals/search?q=robotics&quartile=Q1'`}</code></pre>
      </Section>
    </div>
  );
}
