import { useEffect, useState } from 'react';
import { m } from 'motion/react';

/** A placeholder shaped like the result card, with the current step announced politely. */
export function ResultSkeleton({ steps }: { steps: string[] }) {
  const [step, setStep] = useState(0);
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const stepTimer = window.setInterval(() => setStep(s => Math.min(s + 1, steps.length - 1)), 2500);
    const slowTimer = window.setTimeout(() => setSlow(true), 9000);
    return () => { window.clearInterval(stepTimer); window.clearTimeout(slowTimer); };
  }, [steps.length]);

  return (
    <m.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="card overflow-hidden" aria-busy="true">
      <div className="progress-indeterminate h-1 bg-primary-soft" aria-hidden="true" />
      <div role="status" aria-live="polite" className="border-b border-border px-5 py-3 text-sm font-bold text-primary-text sm:px-8">
        {steps[step]}
        {slow && <span className="mt-1 block font-normal text-muted">This is taking longer than usual. The server may be starting up, which can take up to 30 seconds.</span>}
      </div>
      <div className="space-y-4 p-5 sm:p-8" aria-hidden="true">
        <div className="skeleton h-5 w-24 rounded-full" />
        <div className="skeleton h-8 w-4/5" />
        <div className="skeleton h-4 w-2/5" />
        <div className="flex items-center justify-between gap-6 pt-4">
          <div className="flex-1 space-y-3"><div className="skeleton h-6 w-3/5" /><div className="skeleton h-4 w-full" /><div className="skeleton h-4 w-4/5" /></div>
          <div className="skeleton h-20 w-20 rounded-full" />
        </div>
        <div className="grid gap-4 pt-4 sm:grid-cols-2">
          {Array.from({ length: 6 }, (_, i) => <div key={i} className="space-y-2"><div className="skeleton h-3 w-20" /><div className="skeleton h-4 w-3/4" /></div>)}
        </div>
      </div>
    </m.div>
  );
}
