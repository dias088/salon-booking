import { useMemo } from 'react';

import { useAvailability } from '@/api/queries';
import type { Master, Service } from '@/api/types';
import { EmptyState } from '@/components/ui/EmptyState';
import { SlotGridSkeleton } from '@/components/ui/Skeleton';
import { cn } from '@/lib/cn';
import { addDaysIso, formatDate, formatTime, todayIso, weekdayName } from '@/lib/format';

/** Сколько дней показывать в ленте выбора даты. */
const DAYS_AHEAD = 14;

export interface SlotChoice {
  startsAt: string;
  masterId: number;
}

export function StepSlot({
  service,
  master,
  date,
  selected,
  onDateChange,
  onSelect,
}: {
  service: Service;
  /** null — режим «любой свободный мастер». */
  master: Master | null;
  date: string;
  selected: SlotChoice | null;
  onDateChange: (date: string) => void;
  onSelect: (choice: SlotChoice) => void;
}) {
  const { data, isPending, isFetching, isError } = useAvailability(
    service.id,
    date,
    master?.id ?? null,
  );

  const days = useMemo(() => {
    const today = todayIso();
    return Array.from({ length: DAYS_AHEAD }, (_, index) => addDaysIso(today, index));
  }, []);

  const slots = useMemo(() => {
    if (!data) return [];
    if (master) {
      const own = data.masters.find((item) => item.master_id === master.id);
      return (own?.slots ?? []).map((startsAt) => ({ startsAt, masterId: master.id }));
    }
    // «Любой мастер»: берём объединённый список, за слотом закрепляем первого
    // свободного — бэкенд всё равно проверит, что он свободен.
    return data.slots.map((slot) => ({
      startsAt: slot.starts_at,
      masterId: slot.master_ids[0]!,
    }));
  }, [data, master]);

  return (
    <div className="space-y-5">
      <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0">
        {days.map((day) => {
          const isActive = day === date;
          const weekday = weekdayName((new Date(`${day}T00:00:00Z`).getUTCDay() + 6) % 7);
          return (
            <button
              key={day}
              type="button"
              onClick={() => onDateChange(day)}
              aria-pressed={isActive}
              className={cn(
                'flex shrink-0 flex-col items-center rounded-xl border px-3.5 py-2 transition-colors',
                isActive
                  ? 'border-clay-500 bg-clay-500 text-white'
                  : 'border-sand-300 bg-white text-sand-700 hover:bg-sand-100',
              )}
            >
              <span className="text-[11px] uppercase opacity-80">{weekday}</span>
              <span className="tabular text-base font-semibold">{Number(day.slice(8))}</span>
            </button>
          );
        })}
      </div>

      <div>
        <p className="mb-3 text-sm text-sand-600">
          {formatDate(`${date}T12:00:00`)}
          {isFetching && !isPending && <span className="ml-2 text-sand-400">обновляем…</span>}
        </p>

        {isPending ? (
          <SlotGridSkeleton />
        ) : isError ? (
          <EmptyState
            title="Не удалось загрузить расписание"
            description="Попробуйте ещё раз."
          />
        ) : slots.length === 0 ? (
          <EmptyState
            icon="🗓"
            title="На этот день свободного времени нет"
            description={
              master
                ? 'Выберите другую дату или вернитесь назад и попробуйте другого мастера.'
                : 'Выберите другую дату — в этот день все мастера заняты или не работают.'
            }
          />
        ) : (
          <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-6">
            {slots.map((slot) => {
              const isSelected = selected?.startsAt === slot.startsAt;
              return (
                <button
                  key={slot.startsAt}
                  type="button"
                  onClick={() => onSelect(slot)}
                  aria-pressed={isSelected}
                  className={cn(
                    'tabular h-11 rounded-xl border text-sm font-medium transition-colors',
                    isSelected
                      ? 'border-clay-500 bg-clay-500 text-white'
                      : 'border-sand-300 bg-white text-sand-800 hover:border-clay-300 hover:bg-clay-50',
                  )}
                >
                  {formatTime(slot.startsAt)}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
