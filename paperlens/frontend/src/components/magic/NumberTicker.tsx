// Adapted from Magic UI "Number Ticker" (MIT). Counts up once if visible when the page loads;
// otherwise (or with reduced motion) it simply shows the final value, so it never sits at 0.
import { useEffect, useRef } from 'react';
import { useReducedMotion } from 'motion/react';

const DURATION_MS = 1400;
const easeOut = (x: number) => 1 - Math.pow(1 - x, 4);

export function NumberTicker({ value, suffix = '', className }: { value: number; suffix?: string; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const reduce = useReducedMotion();
  const final = value.toLocaleString() + suffix;

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const visible = rect.bottom > 0 && rect.top < window.innerHeight;
    if (reduce || !visible) {
      el.textContent = final;
      return;
    }
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min((now - start) / DURATION_MS, 1);
      el.textContent = Math.round(easeOut(progress) * value).toLocaleString() + suffix;
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => { cancelAnimationFrame(frame); el.textContent = final; };
  }, [reduce, value, suffix, final]);

  // aria-label carries the final number, so screen readers never hear the count.
  return <span ref={ref} className={className} aria-label={final}>{final}</span>;
}
