import type { ReactNode } from 'react';
import { GlowCard } from './GlowCard';
import { m } from 'motion/react';
import { cn } from '../lib/cn';
import { safeUrl } from '../lib/format';
import { t } from '../lib/strings';
import { Icon, type IconName } from './Icon';
import type { Category } from '../types';

export const CATEGORY_STYLE: Record<Category, { cls: string; icon: IconName; key: 'catJournal' | 'catConference' | 'catPreprint' | 'catUnknown' }> = {
  journal: { cls: 'bg-journal-soft text-journal', icon: 'book', key: 'catJournal' },
  conference: { cls: 'bg-conference-soft text-conference', icon: 'users', key: 'catConference' },
  arxiv: { cls: 'bg-preprint-soft text-preprint', icon: 'file', key: 'catPreprint' },
  unknown: { cls: 'bg-surface-2 text-fg', icon: 'info', key: 'catUnknown' },
  error: { cls: 'bg-danger-soft text-danger', icon: 'alert', key: 'catUnknown' },
};

export const QUARTILE_STYLE: Record<string, string> = {
  Q1: 'bg-q1-soft text-q1',
  Q2: 'bg-q2-soft text-q2',
  Q3: 'bg-q3-soft text-q3',
  Q4: 'bg-q4-soft text-q4',
};

export function CategoryBadge({ category }: { category: Category }) {
  const style = CATEGORY_STYLE[category] || CATEGORY_STYLE.unknown;
  return (
    <span className={cn('pill', style.cls)}>
      <Icon name={style.icon} className="h-3.5 w-3.5" />{t(style.key)}
    </span>
  );
}

export function QuartilePill({ quartile }: { quartile: string | null }) {
  return <span className={cn('pill', QUARTILE_STYLE[quartile || ''] || 'bg-surface-2 text-fg')}>{quartile || t('unranked')}</span>;
}

export function ExternalLink({ href, children }: { href: string | null | undefined; children: ReactNode }) {
  const url = safeUrl(href);
  if (!url) return <>{children}</>;
  return (
    <a href={url} rel="noopener noreferrer" target="_blank" className="inline-flex items-center gap-1">
      {children}<span className="sr-only"> ({t('opensNewTab')})</span>
      <Icon name="external" className="h-3.5 w-3.5" />
    </a>
  );
}

/** A primary/secondary/ghost button with a small press response. */
export function Button({ variant = 'secondary', icon, children, className, ...props }:
  { variant?: 'primary' | 'secondary' | 'ghost'; icon?: IconName; children?: ReactNode } &
  Omit<React.ComponentPropsWithoutRef<'button'>, 'onAnimationStart' | 'onDrag' | 'onDragStart' | 'onDragEnd'>) {
  return (
    <m.button type="button" whileTap={{ scale: 0.97 }} transition={{ duration: 0.12 }}
      className={cn(variant === 'primary' ? 'btn-primary' : variant === 'ghost' ? 'btn-ghost' : 'btn-secondary', className)} {...props}>
      {icon && <Icon name={icon} />}{children}
    </m.button>
  );
}

export function Alert({ tone, title, children, role = 'note' }: { tone: 'danger' | 'warning'; title: string; children: ReactNode; role?: string }) {
  const cls = tone === 'danger' ? 'border-danger/40 bg-danger-soft text-danger' : 'border-warning/40 bg-warning-soft text-warning';
  return (
    <div className={cn('flex gap-3 rounded-md border p-4', cls)} role={role}>
      <Icon name="alert" className="mt-0.5 h-5 w-5" />
      <div>
        <p className="font-bold">{title}</p>
        <div className="mt-1 text-sm text-fg">{children}</div>
      </div>
    </div>
  );
}

export function EmptyState({ icon, title, children }: { icon: IconName; title: string; children?: ReactNode }) {
  return (
    <GlowCard innerClassName="flex flex-col items-center px-6 py-12 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-soft text-primary-text">
        <Icon name={icon} className="h-6 w-6" />
      </span>
      <p className="mt-4 font-serif text-xl font-semibold">{title}</p>
      {children && <div className="mt-2 max-w-md text-sm text-muted">{children}</div>}
    </GlowCard>
  );
}
