import { AnimatePresence, m } from 'motion/react';
import { t } from '../../lib/strings';
import { Icon } from '../../components/Icon';
import { CATEGORY_STYLE } from '../../components/ui';
import type { HistoryEntry } from '../../types';

export function History({ items, onRerun, onClear }: { items: HistoryEntry[]; onRerun: (query: string) => void; onClear: () => void }) {
  if (!items.length) return null;
  return (
    <section className="no-print" aria-labelledby="historyHeading">
      <div className="mb-3 flex items-center justify-between gap-4">
        <h2 id="historyHeading" className="flex items-center gap-2 font-sans text-base font-bold"><Icon name="clock" className="h-5 w-5 text-muted" />Recent classifications</h2>
        <button type="button" className="btn-ghost text-sm" onClick={onClear}>Clear</button>
      </div>
      <ul className="divide-y divide-border overflow-hidden rounded-lg border border-border bg-surface">
        <AnimatePresence initial={false}>
          {items.map(item => {
            const meta = [t(CATEGORY_STYLE[item.category]?.key || 'catUnknown'), item.venue, item.rank].filter(Boolean).join(' · ');
            const body = (
              <span className="flex min-w-0 flex-col items-start text-left">
                <span className="max-w-full truncate font-bold">{item.title}</span>
                <span className="max-w-full truncate text-xs text-muted">{meta}</span>
              </span>
            );
            return (
              <m.li key={`${item.query}-${item.at}`} layout initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                {item.query ? (
                  <button type="button" onClick={() => onRerun(item.query!)}
                    className="flex min-h-[52px] w-full items-center gap-3 px-4 py-3 transition-colors hover:bg-surface-2">
                    <Icon name="search" className="h-4 w-4 text-muted" />{body}
                  </button>
                ) : (
                  <div className="flex items-center gap-3 px-4 py-3"><Icon name="file" className="h-4 w-4 text-muted" />{body}</div>
                )}
              </m.li>
            );
          })}
        </AnimatePresence>
      </ul>
      <p className="hint mt-2">Stored only in this browser.</p>
    </section>
  );
}
