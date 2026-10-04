import { Logo } from './Icon';

export function Footer() {
  return (
    <footer className="mt-auto border-t border-border bg-surface">
      <div className="container-page flex flex-col gap-4 py-8 text-sm text-muted sm:flex-row sm:items-center sm:justify-between">
        <p className="flex items-center gap-2 font-serif text-base font-semibold text-fg"><Logo className="h-6 w-6" />PaperLens</p>
        <ul className="flex flex-wrap gap-x-6 gap-y-2">
          <li><a href="#/about">About</a></li>
          <li><a href="https://github.com/aniket02829/paperlens" rel="noopener">Source code</a></li>
          <li><a href="https://github.com/aniket02829/paperlens/issues" rel="noopener">Report an issue</a></li>
        </ul>
      </div>
    </footer>
  );
}
