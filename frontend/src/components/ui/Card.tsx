import { type HTMLAttributes } from 'react';

import { cn } from '@/lib/cn';

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('surface p-5', className)} {...props} />;
}

export function CardTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  return <h3 className={cn('text-base font-semibold text-sand-900', className)} {...props} />;
}
