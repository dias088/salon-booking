import { type ReactNode } from 'react';

import { cn } from '@/lib/cn';
import type { AppointmentStatus } from '@/api/types';

export const STATUS_LABELS: Record<AppointmentStatus, string> = {
  booked: 'Записан',
  completed: 'Состоялась',
  cancelled: 'Отменена',
  no_show: 'Не пришёл',
};

/** Цвета статусов. Используются и в бейджах, и в блоках админ-календаря. */
export const STATUS_STYLES: Record<AppointmentStatus, string> = {
  booked: 'bg-clay-100 text-clay-800 border-clay-200',
  completed: 'bg-emerald-50 text-emerald-800 border-emerald-200',
  cancelled: 'bg-sand-100 text-sand-500 border-sand-200 line-through',
  no_show: 'bg-amber-50 text-amber-800 border-amber-200',
};

export function Badge({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium',
        className,
      )}
    >
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: AppointmentStatus }) {
  return <Badge className={STATUS_STYLES[status]}>{STATUS_LABELS[status]}</Badge>;
}
