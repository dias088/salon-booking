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

/**
 * Слоты разбиты по времени суток. Сплошная сетка из тридцати кнопок
 * читается плохо: глазу не за что зацепиться, а «после обеда» — это то,
 * как человек на самом деле выбирает время.
 */
const PARTS_OF_DAY = [
  { key: 'morning', label: 'Утро', until: 12 },
  { key: 'afternoon', label: 'День', until: 17 },
  { key: 'evening', label: 'Вечер', until: 24 },
] as const;

function partOfDay(time: string): (typeof PARTS_OF_DAY)[number] {
  const hour = Number(time.slice(0, 2));
  return PARTS_OF_DAY.find((part) => hour < part.until) ?? PARTS_OF_DAY[2];
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

  const grouped = useMemo(() => {
    const buckets = new Map<string, { label: string; slots: SlotChoice[] }>();
    for (const slot of slots) {
      const part = partOfDay(formatTime(slot.startsAt));
      const bucket = buckets.get(part.key) ?? { label: part.label, slots: [] };
      bucket.slots.push(slot);
      buckets.set(part.key, bucket);
    }
    // Порядок задаём константой, а не вставкой: утро всегда перед вечером.
    return PARTS_OF_DAY.map((part) => buckets.get(part.key)).filter(
      (bucket): bucket is { label: string; slots: SlotChoice[] } => bucket !== undefined,
    );
  }, [slots]);

  return (
    <div className="space-y-5">
      <div className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 sm:mx-0 sm:px-0">
        {days.map((day) => {
          const isActive = day === date;
          const isToday = day === todayIso();
          const weekday = weekdayName((new Date(`${day}T00:00:00Z`).getUTCDay() + 6) % 7);
          const isWeekend = weekday === 'сб' || weekday === 'вс';
          return (
            <button
              key={day}
              type="button"
              onClick={() => onDateChange(day)}
              aria-pressed={isActive}
              aria-label={formatDate(`${day}T12:00:00`)}
              className={cn(
                'relative flex w-14 shrink-0 flex-col items-center rounded-xl border py-2',
                'transition-all duration-150 ease-out',
                isActive
                  ? 'border-clay-600 bg-clay-600 text-white shadow-accent'
                  : 'border-sand-200 bg-white shadow-card hover:-translate-y-px hover:border-clay-300 hover:shadow-lift',
                !isActive && isWeekend && 'text-clay-700',
                !isActive && !isWeekend && 'text-sand-700',
              )}
            >
              <span className="text-[11px] uppercase opacity-70">{weekday}</span>
              <span className="tabular text-base font-semibold">{Number(day.slice(8))}</span>
              {/* Точка под числом отмечает сегодняшний день. */}
              <span
                className={cn(
                  'mt-1 size-1 rounded-full',
                  isToday ? (isActive ? 'bg-white' : 'bg-clay-500') : 'bg-transparent',
                )}
              />
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
          <div className="space-y-5">
            {grouped.map((bucket) => (
              <div key={bucket.label}>
                <div className="mb-2.5 flex items-center gap-3">
                  <span className="text-xs font-semibold tracking-wide text-sand-500 uppercase">
                    {bucket.label}
                  </span>
                  <span className="h-px flex-1 bg-sand-200" />
                  <span className="tabular text-xs text-sand-400">{bucket.slots.length}</span>
                </div>

                <div className="grid grid-cols-3 gap-2 sm:grid-cols-5 lg:grid-cols-6">
                  {bucket.slots.map((slot) => {
                    const isSelected = selected?.startsAt === slot.startsAt;
                    return (
                      <button
                        key={slot.startsAt}
                        type="button"
                        onClick={() => onSelect(slot)}
                        aria-pressed={isSelected}
                        className={cn(
                          'tabular h-11 rounded-xl border text-sm font-medium',
                          'transition-all duration-150 ease-out',
                          isSelected
                            ? 'border-clay-600 bg-clay-600 text-white shadow-accent'
                            : 'border-sand-200 bg-white text-sand-800 shadow-card hover:-translate-y-px hover:border-clay-300 hover:text-clay-800 hover:shadow-lift',
                        )}
                      >
                        {formatTime(slot.startsAt)}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
