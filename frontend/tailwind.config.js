/** @type {import('tailwindcss').Config} */
// Every colour, radius and shadow comes from the CSS variables in src/styles/tokens.css,
// so light and dark themes share one set of class names.
const token = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}', '../templates/**/*.html'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        bg: token('bg'),
        surface: token('surface'),
        'surface-2': token('surface-2'),
        border: token('border'),
        'border-strong': token('border-strong'),
        fg: token('fg'),
        muted: token('muted'),
        primary: { DEFAULT: token('primary'), hover: token('primary-hover'), fg: token('on-primary'), soft: token('primary-soft'), text: token('primary-text') },
        accent: { DEFAULT: token('accent'), soft: token('accent-soft') },
        ring: token('ring'),
        journal: { DEFAULT: token('journal'), soft: token('journal-soft') },
        conference: { DEFAULT: token('conference'), soft: token('conference-soft') },
        preprint: { DEFAULT: token('preprint'), soft: token('preprint-soft') },
        q1: { DEFAULT: token('q1'), soft: token('q1-soft') },
        q2: { DEFAULT: token('q2'), soft: token('q2-soft') },
        q3: { DEFAULT: token('q3'), soft: token('q3-soft') },
        q4: { DEFAULT: token('q4'), soft: token('q4-soft') },
        success: { DEFAULT: token('success'), soft: token('success-soft') },
        warning: { DEFAULT: token('warning'), soft: token('warning-soft') },
        danger: { DEFAULT: token('danger'), soft: token('danger-soft') },
      },
      fontFamily: {
        serif: ['"Crimson Pro"', 'Georgia', 'Cambria', '"Times New Roman"', 'serif'],
        sans: ['"Atkinson Hyperlegible"', 'ui-sans-serif', 'system-ui', '-apple-system', '"Segoe UI"', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Consolas', 'monospace'],
      },
      fontSize: {
        // Display sizes for serif headings; body sizes keep Tailwind defaults (base = 16px).
        'display-sm': ['2rem', { lineHeight: '1.15', letterSpacing: '-0.01em' }],
        'display-md': ['2.5rem', { lineHeight: '1.1', letterSpacing: '-0.015em' }],
        'display-lg': ['3.25rem', { lineHeight: '1.05', letterSpacing: '-0.02em' }],
      },
      borderRadius: { sm: 'var(--radius-sm)', DEFAULT: 'var(--radius-md)', md: 'var(--radius-md)', lg: 'var(--radius-lg)', xl: 'var(--radius-xl)' },
      boxShadow: { sm: 'var(--shadow-sm)', DEFAULT: 'var(--shadow-md)', md: 'var(--shadow-md)', lg: 'var(--shadow-lg)' },
      maxWidth: { content: '72rem' },
      transitionTimingFunction: { out: 'cubic-bezier(0.22, 1, 0.36, 1)' },
    },
  },
  plugins: [],
};
