import { useEffect, useState, type ReactNode } from 'react';
import BorderGlow from './reactbits/BorderGlow';
import { cn } from '../lib/cn';

// React Bits BorderGlow, coloured with the PaperLens palette (tokens.css): navy, citation
// gold and primary blue. The background must be the real surface colour, because
// BorderGlow switches to its light-surface blend mode only when it sees a light hex.
const THEME = {
  light: { background: '#FFFFFF', glowColor: '26 90 45', colors: ['#1E3A5F', '#B45309', '#3B69A8'] },
  dark: { background: '#111929', glowColor: '32 84 68', colors: ['#93BBF0', '#F2B46B', '#3B69A8'] },
};

function useIsDark() {
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'));
  useEffect(() => {
    const observer = new MutationObserver(() => setDark(document.documentElement.classList.contains('dark')));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);
  return dark;
}

/** A card box with the BorderGlow edge effect. innerClassName styles the content area. */
export function GlowCard({ children, className, innerClassName }: { children: ReactNode; className?: string; innerClassName?: string }) {
  const theme = THEME[useIsDark() ? 'dark' : 'light'];
  return (
    <BorderGlow
      className={cn('text-fg', className)}
      edgeSensitivity={30}
      glowColor={theme.glowColor}
      backgroundColor={theme.background}
      borderRadius={14}
      glowRadius={40}
      glowIntensity={1.0}
      coneSpread={25}
      animated={false}
      colors={theme.colors}
    >
      <div className={cn('min-w-0 overflow-hidden rounded-[13px]', innerClassName)}>{children}</div>
    </BorderGlow>
  );
}
