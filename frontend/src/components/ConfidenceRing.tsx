import { m } from 'motion/react';
import { cn } from '../lib/cn';
import { percent } from '../lib/format';
import { t } from '../lib/strings';

export function confidenceLevel(confidence: number) {
  const pct = percent(confidence);
  return pct >= 80 ? 'high' : pct >= 60 ? 'medium' : 'low';
}

const RING = { high: 'text-success', medium: 'text-warning', low: 'text-danger' } as const;

/** The confidence score as a ring, with the level spelled out (never colour alone). */
export function ConfidenceRing({ confidence }: { confidence: number }) {
  const pct = percent(confidence);
  const level = confidenceLevel(confidence);
  return (
    <div className="flex shrink-0 flex-col items-center">
      <div className="relative">
        <svg viewBox="0 0 36 36" className="h-20 w-20 -rotate-90" aria-hidden="true">
          <circle cx="18" cy="18" r="15.9155" fill="none" strokeWidth="3" className="stroke-surface-2" />
          <m.circle cx="18" cy="18" r="15.9155" fill="none" strokeWidth="3" strokeLinecap="round"
            className={cn('stroke-current', RING[level])}
            initial={{ pathLength: 0 }} animate={{ pathLength: pct / 100 }}
            transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1], delay: 0.15 }} />
        </svg>
        <span className="absolute inset-0 flex items-center justify-center font-serif text-xl font-semibold">{pct}%</span>
      </div>
      <p className={cn('mt-1 text-sm font-bold', RING[level])}>{t(`confidence_${level}`)}</p>
      <p className="sr-only">{t('confidenceSr', { pct, level: t(`confidence_${level}`) })}</p>
    </div>
  );
}
