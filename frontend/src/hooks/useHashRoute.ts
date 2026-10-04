import { useEffect, useState } from 'react';

export const VIEWS = ['analyze', 'journals', 'compare', 'about'] as const;
export type View = (typeof VIEWS)[number];

function viewFromHash(): View {
  const match = location.hash.match(/^#\/(\w+)/);
  const view = match?.[1] as View | undefined;
  return view && VIEWS.includes(view) ? view : 'analyze';
}

/** The current view from the URL hash (#/journals), kept in sync with back/forward. */
export function useHashRoute(): View {
  const [view, setView] = useState<View>(viewFromHash);
  useEffect(() => {
    const onChange = () => setView(viewFromHash());
    window.addEventListener('hashchange', onChange);
    return () => window.removeEventListener('hashchange', onChange);
  }, []);
  return view;
}
