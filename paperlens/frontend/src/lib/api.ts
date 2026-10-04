import { t } from './strings';

/** fetch() that resolves to parsed JSON or throws an Error with a readable message. */
export async function api<T>(url: string, options: RequestInit = {}, timeoutMs = 90000): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  let response: Response;
  try {
    response = await fetch(url, { ...options, signal: controller.signal });
  } catch (e) {
    throw new Error((e as Error).name === 'AbortError' ? t('errTimeout') : t('errNetwork'));
  } finally {
    clearTimeout(timer);
  }
  let data: { success?: boolean; error?: string } & Record<string, unknown>;
  try {
    data = await response.json();
  } catch {
    throw new Error(response.status >= 500 ? t('errServer') : t('errNetwork'));
  }
  if (!response.ok || data.success === false) {
    throw new Error(data.error || t('errServer'));
  }
  return data as T;
}
