import { Component, Suspense, lazy, useEffect, useRef, type ReactNode } from 'react';
import { AnimatePresence, LazyMotion, MotionConfig, domMax, m } from 'motion/react';
import { Header } from './components/Header';
import { Footer } from './components/Footer';
import { ToastProvider } from './components/Toast';
import { CompareProvider } from './state/compare';
import { useHashRoute, type View } from './hooks/useHashRoute';
import { t } from './lib/strings';
import { AnalyzeView } from './views/analyze/AnalyzeView';

// Animation features are bundled, not lazy-loaded: content starts at opacity 0 and exit
// animations gate what is shown next, so a late or failed chunk would hide results.
// The secondary views are split out instead: they are only needed after navigation.
const JournalsView = lazy(() => import('./views/JournalsView').then(mod => ({ default: mod.JournalsView })));
const CompareView = lazy(() => import('./views/CompareView').then(mod => ({ default: mod.CompareView })));
const AboutView = lazy(() => import('./views/AboutView').then(mod => ({ default: mod.AboutView })));

function ViewFallback() {
  return <p className="container-page py-16 text-center text-muted" role="status">{t('viewLoading')}</p>;
}

/** Shown if a view's chunk fails to load (offline, or a deploy replaced the hashed files). */
class ViewBoundary extends Component<{ children: ReactNode; view: View }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidUpdate(prev: { view: View }) {
    if (prev.view !== this.props.view && this.state.failed) this.setState({ failed: false });
  }
  render() {
    if (this.state.failed) return <p className="container-page py-16 text-center text-danger" role="alert">{t('viewFailed')}</p>;
    return this.props.children;
  }
}

const TITLES: Record<View, string> = {
  analyze: t('pageTitle'),
  journals: `${t('navJournals')} · PaperLens`,
  compare: `${t('navCompare')} · PaperLens`,
  about: `${t('navAbout')} · PaperLens`,
};

function CurrentView({ view }: { view: View }) {
  switch (view) {
    case 'journals': return <JournalsView />;
    case 'compare': return <CompareView />;
    case 'about': return <AboutView />;
    default: return <AnalyzeView />;
  }
}

export function App() {
  const view = useHashRoute();
  const mainRef = useRef<HTMLElement>(null);
  const firstRender = useRef(true);

  useEffect(() => {
    document.title = TITLES[view];
    if (firstRender.current) { firstRender.current = false; return; }
    window.scrollTo({ top: 0 });
  }, [view]);

  // Once the old view has animated out and the new one is mounted, move focus to its
  // heading so screen readers announce the change. A split view may still be loading,
  // so keep looking for the heading for a moment; main gets focus in the meantime.
  const focusHeading = () => {
    let tries = 0;
    const attempt = () => {
      const heading = mainRef.current?.querySelector<HTMLElement>('h1');
      if (heading) { heading.tabIndex = -1; heading.focus({ preventScroll: true }); return; }
      if (tries === 0) mainRef.current?.focus({ preventScroll: true });
      if (++tries < 40) setTimeout(attempt, 50);
    };
    requestAnimationFrame(attempt);
  };

  return (
    <MotionConfig reducedMotion="user">
      <LazyMotion features={domMax} strict>
        <ToastProvider>
          <CompareProvider>
            <a href="#main" onClick={e => { e.preventDefault(); mainRef.current?.focus(); }}
              className="btn-primary sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-[100]">Skip to main content</a>
            {/* overflow-x-clip: the BorderGlow halo extends 40px past each card; clip (not hidden)
                keeps the sticky header working. */}
            <div className="flex min-h-screen flex-col overflow-x-clip">
              <Header view={view} />
              <main id="main" ref={mainRef} tabIndex={-1} className="flex-grow focus:outline-none">
                <AnimatePresence mode="wait" initial={false} onExitComplete={focusHeading}>
                  <m.div key={view} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}>
                    <ViewBoundary view={view}>
                      <Suspense fallback={<ViewFallback />}>
                        <CurrentView view={view} />
                      </Suspense>
                    </ViewBoundary>
                  </m.div>
                </AnimatePresence>
              </main>
              <Footer />
            </div>
          </CompareProvider>
        </ToastProvider>
      </LazyMotion>
    </MotionConfig>
  );
}
