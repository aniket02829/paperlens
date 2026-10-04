import { m } from 'motion/react';
import { GlowCard } from '../../components/GlowCard';
import { Icon, type IconName } from '../../components/Icon';
import { BlurFade } from '../../components/magic/BlurFade';

const OUTCOMES: { icon: IconName; title: string; tint: string; body: string; extra: React.ReactNode }[] = [
  {
    icon: 'book', title: 'Journal article', tint: 'bg-journal-soft text-journal',
    body: 'Ranked by the Scimago Journal Rank (SJR) quartile within its subject category.',
    extra: (
      <>
        <ul className="mt-4 grid grid-cols-4 gap-2 text-center text-sm font-bold" aria-label="Journal quartiles">
          <li className="rounded py-2 bg-q1-soft text-q1">Q1</li><li className="rounded py-2 bg-q2-soft text-q2">Q2</li>
          <li className="rounded py-2 bg-q3-soft text-q3">Q3</li><li className="rounded py-2 bg-q4-soft text-q4">Q4</li>
        </ul>
        <p className="mt-3 text-xs text-muted">Q1 denotes the top 25% of journals in the field.</p>
      </>
    ),
  },
  {
    icon: 'users', title: 'Conference paper', tint: 'bg-conference-soft text-conference',
    body: 'Categorised by conference type, with the CORE ranking where available.',
    extra: (
      <>
        <ul className="mt-4 grid grid-cols-3 gap-2 text-center text-sm font-bold" aria-label="Conference types">
          <li className="rounded bg-surface-2 py-2">IEEE</li><li className="rounded bg-surface-2 py-2">International</li><li className="rounded bg-surface-2 py-2">National</li>
        </ul>
        <p className="mt-3 text-xs text-muted">CORE ranks: A* (flagship), A, B and C.</p>
      </>
    ),
  },
  {
    icon: 'file', title: 'Preprint (arXiv)', tint: 'bg-preprint-soft text-preprint',
    body: 'Identified as not yet peer reviewed. Suitable ranked journals in the paper’s subject are recommended for submission.',
    extra: <p className="mt-4 text-sm text-muted">Preprints that were later published are matched to their published version.</p>,
  },
];

const STEPS = [
  { n: '01', title: 'Document analysis', body: 'The document is parsed for its DOI, arXiv identifier, ISSN and ISBN, together with structural evidence such as review dates and proceedings statements.' },
  { n: '02', title: 'Metadata verification', body: 'The identifiers are verified against CrossRef, OpenAlex, Semantic Scholar and arXiv to establish where the paper was actually published.' },
  { n: '03', title: 'Ranking and verification', body: 'The venue is matched to the Scimago journal rankings or the CORE conference rankings and checked against the Scopus source list, DOAJ and the hijacked and predatory journal lists. The evidence is reported with a confidence score.' },
];

const SOURCES = ['Scimago Journal Rank', 'CORE Rankings', 'Scopus source list', 'DOAJ', 'Retraction Watch', 'CrossRef', 'OpenAlex', 'Semantic Scholar', 'arXiv'];

export function Landing() {
  return (
    <>
      <section className="container-page pt-20" aria-labelledby="outcomesHeading">
        <BlurFade>
          <p className="eyebrow">What you receive</p>
          <h2 id="outcomesHeading" className="mt-2 text-display-sm font-semibold">Classification outcomes</h2>
          <p className="mt-3 max-w-2xl text-muted">Every paper is assigned to one of three categories, each with the ranking information relevant to it.</p>
        </BlurFade>
        <ul className="mt-10 grid gap-5 md:grid-cols-3">
          {OUTCOMES.map((o, i) => (
            <BlurFade as="li" key={o.title} delay={i * 0.08} className="h-full">
              <GlowCard className="h-full" innerClassName="h-full p-6">
              <div className="flex items-center gap-3">
                <span className={`flex h-10 w-10 items-center justify-center rounded-md ${o.tint}`}><Icon name={o.icon} className="h-5 w-5" /></span>
                <h3 className="text-xl font-semibold">{o.title}</h3>
              </div>
              <p className="mt-4 text-sm text-muted">{o.body}</p>
              {o.extra}
              </GlowCard>
            </BlurFade>
          ))}
        </ul>
      </section>

      <section className="container-page pb-24 pt-20" aria-labelledby="methodHeading">
        <BlurFade>
          <p className="eyebrow">How it works</p>
          <h2 id="methodHeading" className="mt-2 text-display-sm font-semibold">Methodology</h2>
        </BlurFade>
        <ol className="mt-10 grid gap-8 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <BlurFade as="li" key={s.n} delay={i * 0.08} className="relative border-t-2 border-primary pt-5 dark:border-primary-text">
              <p className="font-serif text-3xl font-semibold text-accent">{s.n}</p>
              <h3 className="mt-2 font-sans text-base font-bold">{s.title}</h3>
              <p className="mt-2 text-sm text-muted">{s.body}</p>
            </BlurFade>
          ))}
        </ol>
        <BlurFade className="mt-16 border-t border-border pt-8">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-muted">Data sources</p>
          <m.ul className="mt-4 flex flex-wrap gap-x-8 gap-y-3 text-sm font-bold text-fg">
            {SOURCES.map(s => <li key={s} className="flex items-center gap-2"><Icon name="database" className="h-4 w-4 text-muted" />{s}</li>)}
          </m.ul>
        </BlurFade>
      </section>
    </>
  );
}
