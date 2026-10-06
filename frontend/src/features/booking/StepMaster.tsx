import { useMasters } from '@/api/queries';
import type { Master, Service } from '@/api/types';
import { Avatar } from '@/components/ui/Avatar';
import { EmptyState } from '@/components/ui/EmptyState';
import { RowsSkeleton } from '@/components/ui/Skeleton';
import { cn } from '@/lib/cn';
import { formatDuration, formatMoney, plural } from '@/lib/format';

/** null в выборе мастера означает «любой свободный». */
export type MasterChoice = Master | null;

export function StepMaster({
  service,
  selected,
  anyMaster,
  onSelect,
}: {
  service: Service;
  selected: MasterChoice;
  anyMaster: boolean;
  onSelect: (master: MasterChoice) => void;
}) {
  const { data, isPending, isError } = useMasters(service.id);
  const masters = data?.items ?? [];

  if (isPending) return <RowsSkeleton rows={3} />;

  if (isError || masters.length === 0) {
    return (
      <EmptyState
        title="Эту услугу пока никто не оказывает"
        description="Выберите другую услугу или позвоните в салон."
      />
    );
  }

  return (
    <div className="space-y-3">
      <button
        type="button"
        onClick={() => onSelect(null)}
        aria-pressed={anyMaster}
        className={cn(
          'flex w-full items-center gap-4 rounded-2xl border p-4 text-left transition-colors',
          anyMaster
            ? 'border-clay-500 bg-clay-50 ring-1 ring-clay-300'
            : 'border-sand-200 bg-white hover:border-sand-300 hover:bg-sand-50',
        )}
      >
        <span
          aria-hidden="true"
          className="flex size-12 shrink-0 items-center justify-center rounded-full bg-sand-200 text-lg text-sand-600"
        >
          ✦
        </span>
        <span className="min-w-0">
          <span className="block font-medium text-sand-900">Любой свободный мастер</span>
          <span className="block text-sm text-sand-600">
            Покажем все свободные окна — {masters.length}{' '}
            {plural(masters.length, 'мастер', 'мастера', 'мастеров')}
          </span>
        </span>
      </button>

      {masters.map((master) => {
        const offer = master.services.find((item) => item.service_id === service.id);
        const isSelected = !anyMaster && selected?.id === master.id;
        return (
          <button
            key={master.id}
            type="button"
            onClick={() => onSelect(master)}
            aria-pressed={isSelected}
            className={cn(
              'flex w-full items-center gap-4 rounded-2xl border p-4 text-left transition-colors',
              isSelected
                ? 'border-clay-500 bg-clay-50 ring-1 ring-clay-300'
                : 'border-sand-200 bg-white hover:border-sand-300 hover:bg-sand-50',
            )}
          >
            <Avatar name={master.full_name} photoUrl={master.photo_url} />
            <span className="min-w-0 flex-1">
              <span className="block font-medium text-sand-900">{master.full_name}</span>
              {master.bio && (
                <span className="line-clamp-2 block text-sm text-sand-600">{master.bio}</span>
              )}
            </span>
            {offer && (
              <span className="tabular shrink-0 text-right">
                <span className="block font-semibold text-clay-700">
                  {formatMoney(offer.price)}
                </span>
                <span className="block text-xs text-sand-500">
                  {formatDuration(offer.duration_min)}
                </span>
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
