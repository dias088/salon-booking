import { useState } from 'react';

import { useMasterSchedule, useSetAppointmentStatus } from '@/api/adminQueries';
import type { Appointment, AppointmentStatus } from '@/api/types';
import { RequireRole } from '@/components/RequireRole';
import { STATUS_LABELS, StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DayPicker } from '@/components/ui/DayPicker';
import { EmptyState } from '@/components/ui/EmptyState';
import { RowsSkeleton } from '@/components/ui/Skeleton';
import { useToast } from '@/components/ui/Toast';
import { ApiError } from '@/lib/api';
import { cn } from '@/lib/cn';
import {
  addDaysIso,
  formatDateWithWeekday,
  formatMoney,
  formatTime,
  plural,
  todayIso,
  toIsoDate,
  weekdayIndex,
} from '@/lib/format';

/** Мастер отмечает только факт визита; отмена — к администратору. */
const MASTER_STATUSES: AppointmentStatus[] = ['completed', 'no_show'];

export function MasterSchedulePage() {
  return (
    <RequireRole roles={['master']}>
      <Schedule />
    </RequireRole>
  );
}

function Schedule() {
  const [mode, setMode] = useState<'day' | 'week'>('day');
  const [date, setDate] = useState(todayIso());

  // Неделя считается от понедельника, как и weekday в графике мастера.
  const weekStart = addDaysIso(date, -weekdayIndex(`${date}T12:00:00`));
  const from = mode === 'day' ? date : weekStart;
  const to = mode === 'day' ? date : addDaysIso(weekStart, 6);

  const { data, isPending } = useMasterSchedule(from, to);
  const items = data?.items ?? [];

  const byDay = new Map<string, Appointment[]>();
  for (const appointment of items) {
    const day = toIsoDate(appointment.starts_at);
    byDay.set(day, [...(byDay.get(day) ?? []), appointment]);
  }

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold text-sand-900">Моё расписание</h1>
        <div className="flex gap-2">
          {(['day', 'week'] as const).map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setMode(value)}
              aria-pressed={mode === value}
              className={cn(
                'rounded-full border px-4 py-2 text-sm font-medium transition-colors',
                mode === value
                  ? 'border-clay-500 bg-clay-500 text-white'
                  : 'border-sand-300 bg-white text-sand-700 hover:bg-sand-100',
              )}
            >
              {value === 'day' ? 'День' : 'Неделя'}
            </button>
          ))}
        </div>
      </header>

      <DayPicker value={date} onChange={setDate} />

      {isPending ? (
        <RowsSkeleton rows={4} />
      ) : items.length === 0 ? (
        <EmptyState
          icon="🗓"
          title="Записей нет"
          description={mode === 'day' ? 'На этот день вы свободны.' : 'На этой неделе пусто.'}
        />
      ) : (
        <div className="space-y-6">
          <p className="text-sm text-sand-600">
            {items.length} {plural(items.length, 'запись', 'записи', 'записей')}
          </p>
          {[...byDay.entries()]
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([day, dayItems]) => (
              <section key={day} className="space-y-2">
                <h2 className="text-sm font-semibold text-sand-700">
                  {formatDateWithWeekday(`${day}T12:00:00`)}
                </h2>
                <ul className="space-y-2">
                  {dayItems.map((appointment) => (
                    <ScheduleRow key={appointment.id} appointment={appointment} />
                  ))}
                </ul>
              </section>
            ))}
        </div>
      )}
    </div>
  );
}

function ScheduleRow({ appointment }: { appointment: Appointment }) {
  const setStatus = useSetAppointmentStatus('master');
  const toast = useToast();

  const mark = async (status: AppointmentStatus) => {
    try {
      await setStatus.mutateAsync({ id: appointment.id, status });
      toast.success(`Отмечено: ${STATUS_LABELS[status].toLowerCase()}`);
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : 'Не удалось изменить статус');
    }
  };

  return (
    <li className="flex flex-wrap items-center gap-4 rounded-2xl border border-sand-200 bg-white p-4">
      <span className="tabular w-20 shrink-0 font-semibold text-sand-900">
        {formatTime(appointment.starts_at)}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block font-medium text-sand-900">{appointment.service_name}</span>
        <span className="block text-sm text-sand-600">
          {appointment.client_name} · {appointment.client_phone}
        </span>
        {appointment.comment && (
          <span className="mt-1 block text-sm text-sand-500">{appointment.comment}</span>
        )}
      </span>
      <span className="tabular shrink-0 text-sm text-sand-700">
        {formatMoney(appointment.price_at_booking)}
      </span>
      <StatusBadge status={appointment.status} />
      {appointment.status === 'booked' && (
        <span className="flex shrink-0 gap-2">
          {MASTER_STATUSES.map((status) => (
            <Button
              key={status}
              size="sm"
              variant="secondary"
              loading={setStatus.isPending}
              onClick={() => void mark(status)}
            >
              {STATUS_LABELS[status]}
            </Button>
          ))}
        </span>
      )}
    </li>
  );
}
