// Adapted from Magic UI "Blur Fade" (MIT): fades content up into place once it scrolls into view.
import type { ReactNode } from 'react';
import { m } from 'motion/react';

export function BlurFade({ children, delay = 0, className, as = 'div' }:
  { children: ReactNode; delay?: number; className?: string; as?: 'div' | 'li' | 'section' }) {
  const Tag = m[as];
  return (
    <Tag
      className={className}
      initial={{ opacity: 0, y: 12, filter: 'blur(4px)' }}
      whileInView={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
      viewport={{ once: true, margin: '0px 0px -40px 0px' }}
      transition={{ duration: 0.45, delay, ease: [0.22, 1, 0.36, 1] }}
    >
      {children}
    </Tag>
  );
}
