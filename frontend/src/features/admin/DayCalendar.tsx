import { useMemo } from 'react';

import type { Appointment, Master } from '@/api/types';
import { STATUS_LABELS, STATUS_STYLES } from '@/components/ui/Badge';
import { cn } from '@/lib/cn';
import { formatMoney, formatTime } from '@/lib/format';

/** Границы сетки календаря. Салон работает с 9 до 21. */
export const DAY_START_HOUR = 9;
export const DAY_END_HOUR = 21;
const MINUTES_PER_ROW = 15;
const ROW_HEIGHT_PX = 16;

const TOTAL_MINUTES = (DAY_END_HOUR - DAY_START_HOUR) * 60;
const TOTAL_HEIGHT = (TOTAL_MINUTES / MINUTES_PER_ROW) * ROW_HEIGHT_PX;

/** Минуты от начала сетки до момента — в поясе салона. */
function minutesFromDayStart(iso: string): number {
  const [hours, minutes] = formatTime(iso).split(':').map(Number);
  return (hours ?? 0) * 60 + (minutes ?? 0) - DAY_START_HOUR * 60;
}

function minutesToTimeLabel(minutes: number): string {
  const total = DAY_START_HOUR * 60 + minutes;
  const hours = Math.floor(total / 60);
  const rest = total % 60;
  return `${String(hours).padStart(2, '0')}:${String(rest).padStart(2, '0')}`;
}

export function DayCalendar({
  date,
  masters,
  appointments,
  onPickEmpty,
  onPickAppointment,
}: {
  date: string;
  masters: Master[];
  appointments: Appointment[];
  /** Клик по свободной ячейке: создать запись на это время у этого мастера. */
  onPickEmpty: (masterId: number, time: string) => void;
  onPickAppointment: (appointment: Appointment) => void;
}) {
  const byMaster = useMemo(() => {
    const map = new Map<number, Appointment[]>();
    for (const appointment of appointments) {
      const list = map.get(appointment.master_id) ?? [];
      list.push(appointment);
      map.set(appointment.master_id, list);
    }
    return map;
  }, [appointments]);

  const hourLines = Array.from(
    { length: DAY_END_HOUR - DAY_START_HOUR + 1 },
    (_, index) => DAY_START_HOUR + index,
  );

  if (masters.length === 0) {
    return <p className="text-sand-600">Нет активных мастеров.</p>;
  }

  return (
    <div className="overflow-x-auto surface">
      <div
        className="min-w-[640px]"
        style={{
          display: 'grid',
          gridTemplateColumns: `3.5rem repeat(${masters.length}, 1fr)`,
        }}
      >
        <div className="sticky top-0 z-10 border-b border-sand-200 bg-white" />
        {masters.map((master) => (
          <div
            key={master.id}
            className="sticky top-0 z-10 truncate border-b border-l border-sand-200 bg-white px-3 py-2.5 text-sm font-medium text-sand-800"
            title={master.full_name}
          >
            {master.full_name}
          </div>
        ))}

        <div className="relative" style={{ height: TOTAL_HEIGHT }}>
          {hourLines.slice(0, -1).map((hour) => (
            <div
              key={hour}
              className="tabular absolute right-2 -translate-y-1/2 text-xs text-sand-400"
              style={{ top: ((hour - DAY_START_HOUR) * 60 * ROW_HEIGHT_PX) / MINUTES_PER_ROW }}
            >
              {String(hour).padStart(2, '0')}:00
            </div>
          ))}
        </div>

        {masters.map((master) => (
          <MasterColumn
            key={master.id}
            date={date}
            master={master}
            appointments={byMaster.get(master.id) ?? []}
            hourLines={hourLines}
            onPickEmpty={onPickEmpty}
            onPickAppointment={onPickAppointment}
          />
        ))}
      </div>
    </div>
  );
}

function MasterColumn({
  master,
  appointments,
  hourLines,
  onPickEmpty,
  onPickAppointment,
}: {
  date: string;
  master: Master;
  appointments: Appointment[];
  hourLines: number[];
  onPickEmpty: (masterId: number, time: string) => void;
  onPickAppointment: (appointment: Appointment) => void;
}) {
  const handleClick = (event: React.MouseEvent<HTMLDivElement>) => {
    // Переводим координату клика в время, округляя вниз до шага сетки.
    const bounds = event.currentTarget.getBoundingClientRect();
    const offsetY = event.clientY - bounds.top;
    const minutes = Math.floor(offsetY / ROW_HEIGHT_PX) * MINUTES_PER_ROW;
    if (minutes < 0 || minutes >= TOTAL_MINUTES) return;
    onPickEmpty(master.id, minutesToTimeLabel(minutes));
  };

  return (
    <div
      className="relative border-l border-sand-200"
      style={{ height: TOTAL_HEIGHT }}
      onClick={handleClick}
      role="presentation"
    >
      {hourLines.map((hour) => (
        <div
          key={hour}
          className="pointer-events-none absolute inset-x-0 border-t border-sand-100"
          style={{ top: ((hour - DAY_START_HOUR) * 60 * ROW_HEIGHT_PX) / MINUTES_PER_ROW }}
        />
      ))}

      {appointments.map((appointment) => {
        const top =
          (minutesFromDayStart(appointment.starts_at) / MINUTES_PER_ROW) * ROW_HEIGHT_PX;
        const height = Math.max(
          (appointment.duration_min / MINUTES_PER_ROW) * ROW_HEIGHT_PX,
          ROW_HEIGHT_PX,
        );
        return (
          <button
            key={appointment.id}
            type="button"
            onClick={(event) => {
              event.stopPropagation();
              onPickAppointment(appointment);
            }}
            title={`${formatTime(appointment.starts_at)} ${appointment.service_name} · ${appointment.client_name} · ${STATUS_LABELS[appointment.status]}`}
            className={cn(
              'absolute inset-x-1 overflow-hidden rounded-md border px-1.5 py-0.5 text-left text-[11px] leading-tight transition-shadow hover:shadow-md',
              STATUS_STYLES[appointment.status],
            )}
            style={{ top, height }}
          >
            <span className="tabular block font-medium">
              {formatTime(appointment.starts_at)} {appointment.client_name}
            </span>
            {height > ROW_HEIGHT_PX * 2 && (
              <span className="block truncate opacity-80">{appointment.service_name}</span>
            )}
            {height > ROW_HEIGHT_PX * 4 && (
              <span className="tabular block opacity-70">
                {formatMoney(appointment.price_at_booking)}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
