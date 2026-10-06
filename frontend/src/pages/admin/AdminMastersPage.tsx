import { useState } from 'react';

import {
  useAddTimeOff,
  useAdminMasters,
  useDeleteTimeOff,
  useMasterDetail,
  useTimeOff,
} from '@/api/adminQueries';
import { Avatar } from '@/components/ui/Avatar';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardTitle } from '@/components/ui/Card';
import { Field } from '@/components/ui/Field';
import { RowsSkeleton } from '@/components/ui/Skeleton';
import { useToast } from '@/components/ui/Toast';
import { ApiError } from '@/lib/api';
import { cn } from '@/lib/cn';
import { addDaysIso, formatDate, plural, todayIso, weekdayName } from '@/lib/format';

export function AdminMastersPage() {
  const { data, isPending } = useAdminMasters();
  const masters = data?.items ?? [];
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const activeId = selectedId ?? masters[0]?.id ?? null;

  if (isPending) return <RowsSkeleton rows={4} />;

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-semibold text-sand-900">Мастера</h1>

      <div className="grid gap-5 lg:grid-cols-[18rem_1fr]">
        <ul className="space-y-2">
          {masters.map((master) => (
            <li key={master.id}>
              <button
                type="button"
                onClick={() => setSelectedId(master.id)}
                className={cn(
                  'flex w-full items-center gap-3 rounded-xl border p-3 text-left transition-colors',
                  master.id === activeId
                    ? 'border-clay-400 bg-clay-50'
                    : 'border-sand-200 bg-white hover:bg-sand-50',
                )}
              >
                <Avatar
                  name={master.full_name}
                  photoUrl={master.photo_url}
                  className="size-9 text-xs"
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-sand-900">
                    {master.full_name}
                  </span>
                  <span className="block text-xs text-sand-500">
                    {master.services.length}{' '}
                    {plural(master.services.length, 'услуга', 'услуги', 'услуг')}
                  </span>
                </span>
                {!master.is_active && (
                  <Badge className="border-sand-200 bg-sand-100 text-sand-500">off</Badge>
                )}
              </button>
            </li>
          ))}
        </ul>

        {activeId !== null && <MasterPanel masterId={activeId} />}
      </div>
    </div>
  );
}

function MasterPanel({ masterId }: { masterId: number }) {
  const { data: master } = useMasterDetail(masterId);
  const { data: timeOff } = useTimeOff(masterId);
  const addTimeOff = useAddTimeOff(masterId);
  const deleteTimeOff = useDeleteTimeOff(masterId);
  const toast = useToast();

  const [from, setFrom] = useState(addDaysIso(todayIso(), 7));
  const [to, setTo] = useState(addDaysIso(todayIso(), 14));
  const [reason, setReason] = useState('Отпуск');

  if (!master) return <RowsSkeleton rows={3} />;

  const byWeekday = new Map<number, string[]>();
  for (const hours of master.working_hours) {
    const list = byWeekday.get(hours.weekday) ?? [];
    list.push(`${hours.start_time.slice(0, 5)}–${hours.end_time.slice(0, 5)}`);
    byWeekday.set(hours.weekday, list);
  }

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      // Период задаётся целыми днями: от 00:00 первого до 00:00 следующего
      // после последнего — полуоткрытый интервал, как tstzrange в БД.
      await addTimeOff.mutateAsync({
        starts_at: `${from}T00:00:00+05:00`,
        ends_at: `${addDaysIso(to, 1)}T00:00:00+05:00`,
        reason,
      });
      toast.success('Период отсутствия добавлен');
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : 'Не удалось добавить');
    }
  };

  return (
    <div className="space-y-5">
      <Card>
        <CardTitle>График работы</CardTitle>
        <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
          {Array.from({ length: 7 }, (_, weekday) => {
            const intervals = byWeekday.get(weekday);
            return (
              <div key={weekday} className="flex justify-between gap-4">
                <dt className="text-sand-600">{weekdayName(weekday, true)}</dt>
                <dd className={intervals ? 'tabular text-sand-900' : 'text-sand-400'}>
                  {intervals ? intervals.join(', ') : 'выходной'}
                </dd>
              </div>
            );
          })}
        </dl>
      </Card>

      <Card>
        <CardTitle>Отпуска и выходные</CardTitle>
        <p className="mt-1 text-sm text-sand-500">
          Пересекающиеся периоды не примет база — ограничение
          <code className="ml-1 text-xs">time_off_no_overlap</code>.
        </p>

        {timeOff && timeOff.length > 0 ? (
          <ul className="mt-4 space-y-2">
            {timeOff.map((period) => (
              <li
                key={period.id}
                className="flex items-center justify-between gap-3 rounded-xl border border-sand-200 px-3.5 py-2.5 text-sm"
              >
                <span className="tabular text-sand-800">
                  {formatDate(period.starts_at)} — {formatDate(period.ends_at)}
                  {period.reason && <span className="ml-2 text-sand-500">{period.reason}</span>}
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  loading={deleteTimeOff.isPending}
                  onClick={() => void deleteTimeOff.mutateAsync(period.id)}
                >
                  Удалить
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-4 text-sm text-sand-500">Периодов отсутствия нет.</p>
        )}

        <form onSubmit={submit} className="mt-5 grid gap-3 sm:grid-cols-[1fr_1fr_1fr_auto]">
          <Field
            label="С"
            type="date"
            value={from}
            onChange={(event) => setFrom(event.target.value)}
          />
          <Field
            label="По включительно"
            type="date"
            value={to}
            onChange={(event) => setTo(event.target.value)}
          />
          <Field
            label="Причина"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
          />
          <div className="flex items-end">
            <Button type="submit" loading={addTimeOff.isPending}>
              Добавить
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}
