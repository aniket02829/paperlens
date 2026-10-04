export function formatNumber(n: number | null | undefined): string | null {
  if (n === null || n === undefined) return null;
  return Number(n).toLocaleString();
}

/** Return the URL if it is a plain http(s) link, otherwise null (blocks javascript: etc.). */
export function safeUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'https:' || parsed.protocol === 'http:' ? parsed.href : null;
  } catch {
    return null;
  }
}

/** Quote a CSV cell and stop spreadsheet apps from running it as a formula. */
export function csvCell(value: unknown): string {
  let text = value === null || value === undefined ? '' : String(value);
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return `"${text.replace(/"/g, '""')}"`;
}

export function downloadText(filename: string, text: string, type: string) {
  const blob = new Blob(['﻿' + text], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const percent = (confidence: number | null | undefined) => Math.round((confidence || 0) * 100);
