import { useEffect, useState } from 'react';
import { m } from 'motion/react';
import { cn } from '../lib/cn';
import { Icon, Logo } from './Icon';
import { useCompare } from '../state/compare';
import type { View } from '../hooks/useHashRoute';

const LINKS: { view: View; label: string; short: string }[] = [
  { view: 'analyze', label: 'Classify a paper', short: 'Classify' },
  { view: 'journals', label: 'Journal search', short: 'Journals' },
  { view: 'compare', label: 'Compare', short: 'Compare' },
  { view: 'about', label: 'About', short: 'About' },
];

function useDarkMode(): [boolean, () => void] {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'));
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
  }, [dark]);
  const toggle = () => setDark(d => {
    try { localStorage.setItem('theme', d ? 'light' : 'dark'); } catch { /* storage blocked */ }
    return !d;
  });
  return [dark, toggle];
}

export function Header({ view }: { view: View }) {
  const { ids } = useCompare();
  const [dark, toggleDark] = useDarkMode();
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-surface/90 backdrop-blur supports-[backdrop-filter]:bg-surface/75">
      <div className="container-page flex flex-wrap items-center gap-x-6 gap-y-1 py-2">
        <a href="#/analyze" className="mr-auto flex min-h-[44px] items-center gap-2.5 text-fg no-underline" aria-label="PaperLens home">
          <Logo />
          <span className="font-serif text-xl font-semibold tracking-tight">PaperLens</span>
        </a>
        <button type="button" onClick={toggleDark} aria-pressed={dark}
          className="btn-ghost order-2 px-3 sm:order-3" title={dark ? 'Switch to light mode' : 'Switch to dark mode'}>
          <Icon name={dark ? 'sun' : 'moon'} className="h-5 w-5" />
          <span className="sr-only">Dark mode</span>
        </button>
        <nav aria-label="Main" className="order-3 -mx-2 w-full sm:order-2 sm:mx-0 sm:w-auto">
          <ul className="flex">
            {LINKS.map(link => {
              const active = view === link.view;
              return (
                <li key={link.view} className="flex-1 sm:flex-none">
                  <a href={`#/${link.view}`} aria-current={active ? 'page' : undefined}
                    className={cn('relative flex min-h-[44px] items-center justify-center gap-1.5 whitespace-nowrap px-2 text-sm font-bold no-underline transition-colors sm:px-3',
                      active ? 'text-primary-text' : 'text-muted hover:text-fg')}>
                    <span className="sm:hidden">{link.short}</span>
                    <span className="hidden sm:inline">{link.label}</span>
                    {link.view === 'compare' && ids.length > 0 && (
                      <span className="pill bg-primary px-1.5 py-0 text-primary-fg" aria-label={`${ids.length} selected`}>{ids.length}</span>
                    )}
                    {active && (
                      <m.span layoutId="nav-underline" className="absolute inset-x-2 -bottom-[9px] h-0.5 rounded-full bg-accent sm:inset-x-3"
                        transition={{ type: 'spring', stiffness: 500, damping: 40 }} />
                    )}
                  </a>
                </li>
              );
            })}
          </ul>
        </nav>
      </div>
    </header>
  );
}
