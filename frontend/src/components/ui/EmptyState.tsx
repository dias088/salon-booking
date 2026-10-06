import { type ReactNode } from 'react';

export function EmptyState({
  title,
  description,
  action,
  icon = '✦',
}: {
  title: string;
  description?: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-sand-300 bg-white/60 px-6 py-12 text-center">
      <div className="flex size-12 items-center justify-center rounded-full bg-sand-100 text-xl text-clay-500">
        {icon}
      </div>
      <p className="mt-4 font-medium text-sand-900">{title}</p>
      {description && <p className="mt-1 max-w-sm text-sm text-sand-600">{description}</p>}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
