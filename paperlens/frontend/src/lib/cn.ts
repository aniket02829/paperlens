import { clsx, type ClassValue } from 'clsx';

/** Join class names. Base styles are in Tailwind's components layer, so utilities passed
 *  in className already win by CSS order and no class-merging library is needed. */
export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}
