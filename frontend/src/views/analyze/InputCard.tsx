import { useRef, useState, type DragEvent, type KeyboardEvent } from 'react';
import { GlowCard } from '../../components/GlowCard';
import { AnimatePresence, m } from 'motion/react';
import { cn } from '../../lib/cn';
import { t } from '../../lib/strings';
import { Icon, type IconName } from '../../components/Icon';
import { Button } from '../../components/ui';

export type InputMode = 'search' | 'upload' | 'bulk';

const TABS: { id: InputMode; icon: IconName; label: string; short: string }[] = [
  { id: 'search', icon: 'search', label: 'Identifier or title', short: 'Search' },
  { id: 'upload', icon: 'upload', label: 'Upload document', short: 'Upload' },
  { id: 'bulk', icon: 'files', label: 'Batch upload', short: 'Batch' },
];

const EXAMPLES = [
  { label: 'Journal article', query: '10.1016/j.patcog.2020.107404' },
  { label: 'Conference paper', query: '10.1109/CVPR.2016.90' },
  { label: 'Preprint', query: 'arXiv:2310.06825' },
];

const MAX_FILE_BYTES = 50 * 1024 * 1024;
export const MAX_BULK = 20;
const isAllowed = (file: File) => /\.(pdf|docx)$/i.test(file.name);
const ACCEPT = '.pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document';

interface Props {
  mode: InputMode;
  onModeChange: (mode: InputMode) => void;
  query: string;
  onQueryChange: (query: string) => void;
  busy: boolean;
  onLookup: (query: string) => void;
  onAnalyzeFiles: (files: File[], bulk: boolean) => void;
  onError: (message: string | null) => void;
}

export function InputCard({ mode, onModeChange, query, onQueryChange, busy, onLookup, onAnalyzeFiles, onError }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const tabRefs = useRef<Record<InputMode, HTMLButtonElement | null>>({ search: null, upload: null, bulk: null });
  const queryRef = useRef<HTMLInputElement>(null);

  const selectMode = (next: InputMode, focus = false) => {
    onModeChange(next);
    setFiles([]);
    onError(null);
    if (focus) tabRefs.current[next]?.focus();
  };

  const onTabKey = (e: KeyboardEvent, index: number) => {
    const keys: Record<string, number> = { ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: TABS.length - 1 };
    if (!(e.key in keys)) return;
    e.preventDefault();
    selectMode(TABS[(keys[e.key] + TABS.length) % TABS.length].id, true);
  };

  const addFiles = (list: FileList | null) => {
    onError(null);
    let picked = Array.from(list || []);
    if (!picked.length) return;
    if (mode === 'upload') picked = picked.slice(0, 1);
    const rejected = picked.filter(f => !isAllowed(f));
    const tooBig = picked.filter(f => isAllowed(f) && f.size > MAX_FILE_BYTES);
    picked = picked.filter(f => isAllowed(f) && f.size <= MAX_FILE_BYTES);
    const messages: string[] = [];
    if (rejected.length) messages.push(t('errFileType', { names: rejected.map(f => f.name).join(', ') }));
    if (tooBig.length) messages.push(t('errFileSize', { names: tooBig.map(f => f.name).join(', ') }));
    if (mode === 'bulk') {
      if (files.length + picked.length > MAX_BULK) messages.push(t('errTooManyFiles', { n: MAX_BULK }));
      setFiles([...files, ...picked].slice(0, MAX_BULK));
    } else {
      setFiles(picked);
    }
    if (messages.length) onError(messages.join(' '));
  };

  const submitQuery = (e: React.FormEvent) => {
    e.preventDefault();
    const value = query.trim();
    if (!value) {
      onError(t('errEmptyQuery'));
      queryRef.current?.focus();
      return;
    }
    onLookup(value);
  };

  return (
    <GlowCard innerClassName="p-4 sm:p-6">
      <div role="tablist" aria-label="Input method" className="relative mb-6 flex gap-1 rounded-md bg-surface-2 p-1">
        {TABS.map((tab, index) => {
          const selected = mode === tab.id;
          return (
            <button key={tab.id} ref={el => { tabRefs.current[tab.id] = el; }} role="tab" type="button"
              id={`tab-${tab.id}`} aria-controls={selected ? `panel-${tab.id}` : undefined} aria-selected={selected} tabIndex={selected ? 0 : -1}
              onClick={() => selectMode(tab.id)} onKeyDown={e => onTabKey(e, index)}
              className={cn('relative z-10 flex min-h-[44px] min-w-0 flex-1 items-center justify-center gap-1.5 rounded px-2 text-sm font-bold transition-colors sm:gap-2 sm:px-3',
                selected ? 'text-primary-text' : 'text-muted hover:text-fg')}>
              {selected && (
                <m.span layoutId="input-tab" className="absolute inset-0 -z-10 rounded bg-surface shadow-sm"
                  transition={{ type: 'spring', stiffness: 500, damping: 40 }} />
              )}
              <Icon name={tab.icon} />
              <span className="sm:hidden">{tab.short}</span>
              <span className="hidden sm:inline">{tab.label}</span>
            </button>
          );
        })}
      </div>

      {mode === 'search' && (
        <div role="tabpanel" id="panel-search" aria-labelledby="tab-search">
          <form onSubmit={submitQuery} noValidate>
            <label htmlFor="queryInput" className="label">DOI, arXiv identifier, or paper title</label>
            <div className="flex flex-col gap-2 sm:flex-row">
              <input ref={queryRef} id="queryInput" type="text" className="input" autoComplete="off" spellCheck={false} maxLength={500}
                aria-describedby="queryHint" placeholder="e.g. 10.1109/CVPR.2016.90" value={query} onChange={e => onQueryChange(e.target.value)} />
              <Button type="submit" variant="primary" icon="search" disabled={busy} className="whitespace-nowrap px-6">Classify</Button>
            </div>
            <p id="queryHint" className="hint mt-2">The DOI is normally printed on the first page of the paper, for example “doi.org/10.…”.</p>
            <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
              <span className="text-muted">Examples:</span>
              {EXAMPLES.map(example => (
                <button key={example.label} type="button" disabled={busy}
                  onClick={() => { onQueryChange(example.query); onLookup(example.query); }}
                  className="min-h-[36px] rounded-full border border-border bg-surface px-3 text-xs font-bold text-fg transition-colors hover:border-primary-text hover:text-primary-text">
                  {example.label}
                </button>
              ))}
            </div>
          </form>
        </div>
      )}

      {mode !== 'search' && (
        <div role="tabpanel" id={`panel-${mode}`} aria-labelledby={`tab-${mode}`}>
          <Dropzone bulk={mode === 'bulk'} onFiles={addFiles} />
          <p className="hint mt-3 flex gap-2"><Icon name="shield" className="mt-0.5 h-4 w-4" />
            <span>Documents are processed once and deleted immediately. They are never stored or shared.</span></p>

          <AnimatePresence>
            {files.length > 0 && (
              <m.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-6">
                <h2 className="mb-2 font-sans text-sm font-bold">
                  {mode === 'bulk' ? t('selectedFiles', { n: files.length }) : t('selectedFile')}
                </h2>
                <ul className="max-h-60 space-y-2 overflow-y-auto">
                  {files.map((file, index) => (
                    <li key={`${file.name}-${index}`} className="flex items-center justify-between gap-3 rounded-md border border-border bg-surface-2 p-3">
                      <span className="flex min-w-0 items-center gap-2">
                        <Icon name="file" className="h-5 w-5 text-muted" />
                        <span className="truncate font-bold">{file.name}</span>
                      </span>
                      <span className="flex shrink-0 items-center gap-2">
                        <span className="text-xs text-muted">{(file.size / (1024 * 1024)).toFixed(1)} MB</span>
                        <button type="button" className="btn-ghost px-2" aria-label={t('removeFile', { name: file.name })}
                          onClick={() => setFiles(files.filter((_, i) => i !== index))}>
                          <Icon name="x" />
                        </button>
                      </span>
                    </li>
                  ))}
                </ul>
                <Button variant="primary" icon="search" className="mt-4 w-full px-6 sm:w-auto" disabled={busy}
                  onClick={() => onAnalyzeFiles(files, mode === 'bulk')}>
                  Classify
                </Button>
              </m.div>
            )}
          </AnimatePresence>
        </div>
      )}
    </GlowCard>
  );
}

function Dropzone({ bulk, onFiles }: { bulk: boolean; onFiles: (files: FileList | null) => void }) {
  const [over, setOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const stop = (e: DragEvent) => { e.preventDefault(); e.stopPropagation(); };
  return (
    <label htmlFor={bulk ? 'bulkInput' : 'fileInput'}
      onDragEnter={e => { stop(e); setOver(true); }} onDragOver={e => { stop(e); setOver(true); }}
      onDragLeave={e => { stop(e); setOver(false); }}
      onDrop={e => { stop(e); setOver(false); onFiles(e.dataTransfer.files); }}
      className={cn('flex cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-8 text-center transition-colors focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2 focus-within:ring-offset-surface sm:p-10',
        over ? 'border-primary-text bg-primary-soft' : 'border-border-strong hover:bg-surface-2')}>
      <span className="flex h-12 w-12 items-center justify-center rounded-full bg-primary-soft text-primary-text">
        <Icon name={bulk ? 'files' : 'upload'} className="h-6 w-6" />
      </span>
      <span className="text-base font-bold text-fg">
        {bulk ? 'Select up to 20 PDF or .docx documents' : 'Select a PDF or Word (.docx) document'}
      </span>
      <span className="hint">{bulk ? 'or drag and drop them here · maximum 50 MB in total' : 'or drag and drop it here · maximum 50 MB'}</span>
      <input ref={inputRef} id={bulk ? 'bulkInput' : 'fileInput'} type="file" className="sr-only" accept={ACCEPT} multiple={bulk}
        onChange={e => { onFiles(e.target.files); e.target.value = ''; }} />
    </label>
  );
}
