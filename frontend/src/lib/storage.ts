/** localStorage that never throws (private windows and blocked storage just fall back). */
export const storage = {
  get<T>(key: string, fallback: T): T {
    try {
      const raw = localStorage.getItem(key);
      return raw === null ? fallback : (JSON.parse(raw) as T);
    } catch {
      return fallback;
    }
  },
  set(key: string, value: unknown) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* storage blocked */ }
  },
  remove(key: string) {
    try { localStorage.removeItem(key); } catch { /* storage blocked */ }
  },
};
