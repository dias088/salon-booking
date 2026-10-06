import { useState } from 'react';

import { useCatalog } from '@/api/queries';
import type { Service } from '@/api/types';
import { EmptyState } from '@/components/ui/EmptyState';
import { ServiceCardSkeleton } from '@/components/ui/Skeleton';
import { cn } from '@/lib/cn';
import { formatDuration, formatMoney } from '@/lib/format';

export function StepService({
  selected,
  onSelect,
}: {
  selected: Service | null;
  onSelect: (service: Service) => void;
}) {
  const { data, isPending, isError } = useCatalog();
  const [activeCategory, setActiveCategory] = useState<number | null>(null);

  if (isPending) {
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        {Array.from({ length: 4 }, (_, index) => (
          <ServiceCardSkeleton key={index} />
        ))}
      </div>
    );
  }

  if (isError || !data?.length) {
    return (
      <EmptyState
        title="Каталог пока пуст"
        description="Загляните позже — мы готовим список услуг."
      />
    );
  }

  const categories = data;
  const current = activeCategory ?? categories[0]!.id;
  const services = categories.find((category) => category.id === current)?.services ?? [];

  return (
    <div className="space-y-5">
      {/* Горизонтальная лента категорий — на телефоне это удобнее вкладок. */}
      <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0">
        {categories.map((category) => (
          <button
            key={category.id}
            type="button"
            onClick={() => setActiveCategory(category.id)}
            className={cn(
              'shrink-0 rounded-full border px-4 py-2 text-sm font-medium transition-colors',
              category.id === current
                ? 'border-clay-500 bg-clay-500 text-white'
                : 'border-sand-300 bg-white text-sand-700 hover:bg-sand-100',
            )}
          >
            {category.name}
          </button>
        ))}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {services.map((service) => {
          const isSelected = selected?.id === service.id;
          return (
            <button
              key={service.id}
              type="button"
              onClick={() => onSelect(service)}
              aria-pressed={isSelected}
              className={cn(
                'rounded-2xl border p-5 text-left transition-colors',
                isSelected
                  ? 'border-clay-500 bg-clay-50 ring-1 ring-clay-300'
                  : 'border-sand-200 bg-white hover:border-sand-300 hover:bg-sand-50',
              )}
            >
              <div className="flex items-start justify-between gap-3">
                <h3 className="font-medium text-sand-900">{service.name}</h3>
                <span className="tabular shrink-0 font-semibold text-clay-700">
                  {formatMoney(service.price)}
                </span>
              </div>
              {service.description && (
                <p className="mt-2 text-sm text-sand-600">{service.description}</p>
              )}
              <p className="tabular mt-3 text-sm text-sand-500">
                {formatDuration(service.duration_min)}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
}
