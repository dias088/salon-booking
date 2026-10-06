import { useState } from 'react';

import {
  useAdminMasters,
  useDayAppointments,
  useSetAppointmentStatus,
} from '@/api/adminQueries';
import type { Appointment, AppointmentStatus } from '@/api/types';
import { STATUS_LABELS, STATUS_STYLES, StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { DayPicker } from '@/components/ui/DayPicker';
import { Modal } from '@/components/ui/Modal';
import { Skeleton } from '@/components/ui/Skeleton';
import { useToast } from '@/components/ui/Toast';
import { DayCalendar } from '@/features/admin/DayCalendar';
import {
  QuickBookingDialog,
  type QuickBookingTarget,
} from '@/features/admin/QuickBookingDialog';
import { ApiError } from '@/lib/api';
import { cn } from '@/lib/cn';
import { formatDateWithWeekday, formatMoney, formatTime, todayIso } from '@/lib/format';

const NEXT_STATUSES: AppointmentStatus[] = ['completed', 'no_show', 'cancelled'];

export function AdminCalendarPage() {
  const [date, setDate] = useState(todayIso());
  const [target, setTarget] = useState<QuickBookingTarget | null>(null);
  const [selected, setSelected] = useState<Appointment | null>(null);

  const { data: mastersPage, isPending: mastersPending } = useAdminMasters();
  const { data: dayPage, isPending: dayPending } = useDayAppointments(date);

  const masters = (mastersPage?.items ?? []).filter((master) => master.is_active);
  const appointments = dayPage?.items ?? [];

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold text-sand-900">Календарь дня</h1>
        <DayPicker value={date} onChange={setDate} />
      </header>

      <div className="flex flex-wrap items-center gap-4 text-xs text-sand-600">
        {(Object.keys(STATUS_LABELS) as AppointmentStatus[]).map((status) => (
          <span key={status} className="flex items-center gap-1.5">
            <span className={cn('size-3 rounded border', STATUS_STYLES[status])} />
            {STATUS_LABELS[status]}
          </span>
        ))}
        <span className="ml-auto">Клик по пустому месту — запись по телефону</span>
      </div>

      {mastersPending || dayPending ? (
        <Skeleton className="h-[32rem] rounded-2xl" />
      ) : (
        <DayCalendar
          date={date}
          masters={masters}
          appointments={appointments}
          onPickEmpty={(masterId, time) => {
            const master = masters.find((item) => item.id === masterId);
            if (master) setTarget({ master, date, time });
          }}
          onPickAppointment={setSelected}
        />
      )}

      <QuickBookingDialog target={target} onClose={() => setTarget(null)} />
      <AppointmentDialog appointment={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

function AppointmentDialog({
  appointment,
  onClose,
}: {
  appointment: Appointment | null;
  onClose: () => void;
}) {
  const setStatus = useSetAppointmentStatus('admin');
  const toast = useToast();

  if (!appointment) return null;

  const change = async (status: AppointmentStatus) => {
    try {
      await setStatus.mutateAsync({ id: appointment.id, status });
      toast.success(`Статус: ${STATUS_LABELS[status].toLowerCase()}`);
      onClose();
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : 'Не удалось изменить статус');
    }
  };

  return (
    <Modal open title={appointment.service_name} onClose={onClose}>
      <dl className="space-y-3 text-sm">
        <Row term="Клиент" value={appointment.client_name} />
        <Row term="Телефон" value={appointment.client_phone} />
        <Row term="Мастер" value={appointment.master_name} />
        <Row term="Когда" value={formatDateWithWeekday(appointment.starts_at)} />
        <Row
          term="Время"
          value={`${formatTime(appointment.starts_at)}–${formatTime(appointment.ends_at)}`}
        />
        <Row term="Стоимость" value={formatMoney(appointment.price_at_booking)} />
        <div className="flex items-center justify-between gap-4">
          <dt className="text-sand-500">Статус</dt>
          <dd>
            <StatusBadge status={appointment.status} />
          </dd>
        </div>
      </dl>

      {appointment.comment && (
        <p className="mt-4 rounded-xl bg-sand-100 px-3.5 py-2.5 text-sm text-sand-700">
          {appointment.comment}
        </p>
      )}

      {appointment.status === 'booked' && (
        <div className="mt-5 flex flex-wrap gap-2">
          {NEXT_STATUSES.map((status) => (
            <Button
              key={status}
              size="sm"
              variant={status === 'cancelled' ? 'danger' : 'secondary'}
              loading={setStatus.isPending}
              onClick={() => void change(status)}
            >
              {STATUS_LABELS[status]}
            </Button>
          ))}
        </div>
      )}
    </Modal>
  );
}

function Row({ term, value }: { term: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <dt className="text-sand-500">{term}</dt>
      <dd className="text-right font-medium text-sand-900">{value}</dd>
    </div>
  );
}
