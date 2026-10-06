import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { useCancelAppointment, useMyAppointments } from '@/api/queries';
import type { Appointment } from '@/api/types';
import { StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { RowsSkeleton } from '@/components/ui/Skeleton';
import { useToast } from '@/components/ui/Toast';
import { ApiError } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { cn } from '@/lib/cn';
import { formatDateWithWeekday, formatDuration, formatMoney, formatTime } from '@/lib/format';

const TABS = [
  { value: 'upcoming', label: 'Предстоящие' },
  { value: 'past', label: 'Прошедшие' },
] as const;

export function MyAppointmentsPage() {
  const [tab, setTab] = useState<'upcoming' | 'past'>('upcoming');
  const [searchParams] = useSearchParams();
  const highlightId = Number(searchParams.get('highlight')) || null;

  const { user, loading } = useAuth();
  const { data, isPending } = useMyAppointments(tab);

  if (loading) return <RowsSkeleton rows={3} />;

  if (!user) {
    return (
      <EmptyState
        title="Нужно войти"
        description="Записи привязаны к аккаунту — войдите, чтобы их увидеть."
        action={
          <Link to="/">
            <Button variant="secondary">На главную</Button>
          </Link>
        }
      />
    );
  }

  const items = data?.items ?? [];

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-sand-900">Мои записи</h1>
      </header>

      <div className="flex gap-2">
        {TABS.map((item) => (
          <button
            key={item.value}
            type="button"
            onClick={() => setTab(item.value)}
            aria-pressed={tab === item.value}
            className={cn(
              'rounded-full border px-4 py-2 text-sm font-medium transition-colors',
              tab === item.value
                ? 'border-clay-500 bg-clay-500 text-white'
                : 'border-sand-300 bg-white text-sand-700 hover:bg-sand-100',
            )}
          >
            {item.label}
          </button>
        ))}
      </div>

      {isPending ? (
        <RowsSkeleton rows={3} />
      ) : items.length === 0 ? (
        <EmptyState
          icon="🗓"
          title={tab === 'upcoming' ? 'Предстоящих записей нет' : 'Здесь пока пусто'}
          description={
            tab === 'upcoming'
              ? 'Самое время записаться к мастеру.'
              : 'Ваши визиты появятся тут.'
          }
          action={
            tab === 'upcoming' ? (
              <Link to="/booking">
                <Button>Записаться</Button>
              </Link>
            ) : undefined
          }
        />
      ) : (
        <ul className="space-y-3">
          {items.map((appointment) => (
            <AppointmentCard
              key={appointment.id}
              appointment={appointment}
              highlighted={appointment.id === highlightId}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function AppointmentCard({
  appointment,
  highlighted,
}: {
  appointment: Appointment;
  highlighted: boolean;
}) {
  const cancel = useCancelAppointment();
  const toast = useToast();

  const onCancel = async () => {
    try {
      await cancel.mutateAsync(appointment.id);
      toast.success('Запись отменена');
    } catch (error) {
      toast.error(
        error instanceof ApiError ? error.message : 'Не удалось отменить, попробуйте позже',
      );
    }
  };

  return (
    <li
      className={cn(
        'rounded-2xl border bg-white p-5 transition-colors',
        highlighted ? 'border-clay-400 ring-1 ring-clay-200' : 'border-sand-200',
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-medium text-sand-900">{appointment.service_name}</h2>
          <p className="mt-1 text-sm text-sand-600">{appointment.master_name}</p>
        </div>
        <StatusBadge status={appointment.status} />
      </div>

      <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-3">
        <Row term="Когда" value={formatDateWithWeekday(appointment.starts_at)} />
        <Row
          term="Время"
          value={`${formatTime(appointment.starts_at)} · ${formatDuration(appointment.duration_min)}`}
        />
        <Row term="Стоимость" value={formatMoney(appointment.price_at_booking)} />
      </dl>

      {appointment.comment && (
        <p className="mt-3 rounded-xl bg-sand-100 px-3.5 py-2.5 text-sm text-sand-700">
          {appointment.comment}
        </p>
      )}

      {appointment.can_cancel && (
        <div className="mt-4 flex items-center gap-3">
          <Button
            variant="danger"
            size="sm"
            loading={cancel.isPending}
            onClick={() => void onCancel()}
          >
            Отменить
          </Button>
          <span className="text-xs text-sand-500">Можно до 2 часов до начала</span>
        </div>
      )}
    </li>
  );
}

function Row({ term, value }: { term: string; value: string }) {
  return (
    <div>
      <dt className="text-sand-500">{term}</dt>
      <dd className="tabular font-medium text-sand-900">{value}</dd>
    </div>
  );
}
