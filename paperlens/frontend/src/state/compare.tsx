import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { storage } from '../lib/storage';
import { t } from '../lib/strings';
import { useToast } from '../components/Toast';

const KEY = 'paperlens_compare';
export const MAX_COMPARE = 4;

interface CompareState { ids: number[]; toggle: (id: number) => void; has: (id: number) => boolean }
const CompareContext = createContext<CompareState>({ ids: [], toggle: () => {}, has: () => false });

function initialIds(): number[] {
  // A shared ?compare=1,2 link wins over what this browser had saved.
  const fromUrl = (new URLSearchParams(location.search).get('compare') || '')
    .split(',').map(Number).filter(n => Number.isInteger(n) && n > 0);
  const ids = fromUrl.length ? fromUrl : storage.get<number[]>(KEY, []).filter(Number.isInteger);
  return ids.slice(0, MAX_COMPARE);
}

export function CompareProvider({ children }: { children: ReactNode }) {
  const [ids, setIds] = useState<number[]>(initialIds);
  const toast = useToast();
  useEffect(() => storage.set(KEY, ids), [ids]);

  const toggle = useCallback((id: number) => {
    // Side effects (toasts) stay outside the state updater, which React may call twice.
    if (ids.includes(id)) {
      setIds(ids.filter(x => x !== id));
    } else if (ids.length >= MAX_COMPARE) {
      toast(t('compareFull', { n: MAX_COMPARE }));
    } else {
      setIds([...ids, id]);
      toast(t('addedToCompare'));
    }
  }, [ids, toast]);

  return <CompareContext.Provider value={{ ids, toggle, has: id => ids.includes(id) }}>{children}</CompareContext.Provider>;
}

export const useCompare = () => useContext(CompareContext);
