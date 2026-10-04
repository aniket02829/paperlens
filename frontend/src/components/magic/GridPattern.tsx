// Adapted from Magic UI "Grid Pattern" (MIT): a static SVG grid, faded out at the edges.
import { useId } from 'react';
import { cn } from '../../lib/cn';

export function GridPattern({ size = 32, className }: { size?: number; className?: string }) {
  const id = useId();
  return (
    <svg aria-hidden="true" className={cn('pointer-events-none absolute inset-0 h-full w-full stroke-border', className)}>
      <defs>
        <pattern id={id} width={size} height={size} patternUnits="userSpaceOnUse" x={-1} y={-1}>
          <path d={`M.5 ${size}V.5H${size}`} fill="none" strokeDasharray="0" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" strokeWidth={0} fill={`url(#${id})`} />
    </svg>
  );
}
