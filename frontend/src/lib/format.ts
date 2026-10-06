/**
 * Форматирование дат и денег.
 *
 * Всё время приводится к часовому поясу салона через Intl, а не к поясу
 * браузера: клиент из Москвы, выбирая слот «14:00», должен видеть именно
 * то время, в которое его ждут в Алматы.
 */

export const SALON_TZ = 'Asia/Almaty';

const WEEKDAYS_SHORT = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'];
const WEEKDAYS_FULL = [
  'понедельник',
  'вторник',
  'среда',
  'четверг',
  'пятница',
  'суббота',
  'воскресенье',
];
const MONTHS_GENITIVE = [
  'января',
  'февраля',
  'марта',
  'апреля',
  'мая',
  'июня',
  'июля',
  'августа',
  'сентября',
  'октября',
  'ноября',
  'декабря',
];
const MONTHS_NOMINATIVE = [
  'январь',
  'февраль',
  'март',
  'апрель',
  'май',
  'июнь',
  'июль',
  'август',
  'сентябрь',
  'октябрь',
  'ноябрь',
  'декабрь',
];

function parts(iso: string | Date): {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
} {
  const date = typeof iso === 'string' ? new Date(iso) : iso;
  const formatter = new Intl.DateTimeFormat('en-CA', {
    timeZone: SALON_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
  const found: Record<string, string> = {};
  for (const part of formatter.formatToParts(date)) {
    if (part.type !== 'literal') found[part.type] = part.value;
  }
  return {
    year: Number(found.year),
    month: Number(found.month),
    day: Number(found.day),
    // В en-CA полночь приходит как «24», приводим к нулю.
    hour: Number(found.hour) % 24,
    minute: Number(found.minute),
  };
}

const pad = (value: number): string => String(value).padStart(2, '0');

/** «14:30» в поясе салона. */
export function formatTime(iso: string | Date): string {
  const { hour, minute } = parts(iso);
  return `${pad(hour)}:${pad(minute)}`;
}

/** «12 октября» или «12 октября 2027», если год не текущий. */
export function formatDate(iso: string | Date): string {
  const { year, month, day } = parts(iso);
  const suffix = year === new Date().getFullYear() ? '' : ` ${year}`;
  return `${day} ${MONTHS_GENITIVE[month - 1]}${suffix}`;
}

/** «12 октября, 14:30». */
export function formatDateTime(iso: string | Date): string {
  return `${formatDate(iso)}, ${formatTime(iso)}`;
}

/** «пн, 12 октября». */
export function formatDateWithWeekday(iso: string | Date): string {
  return `${WEEKDAYS_SHORT[weekdayIndex(iso)]}, ${formatDate(iso)}`;
}

export function formatMonth(iso: string): string {
  const [year, month] = iso.split('-');
  return `${MONTHS_NOMINATIVE[Number(month) - 1]} ${year}`;
}

export function formatMonthShort(iso: string): string {
  const [, month] = iso.split('-');
  return (MONTHS_NOMINATIVE[Number(month) - 1] ?? '').slice(0, 3);
}

/** 0 — понедельник, как в working_hours.weekday на бэкенде. */
export function weekdayIndex(iso: string | Date): number {
  const { year, month, day } = parts(iso);
  const utc = new Date(Date.UTC(year, month - 1, day));
  return (utc.getUTCDay() + 6) % 7;
}

export function weekdayName(index: number, full = false): string {
  return (full ? WEEKDAYS_FULL : WEEKDAYS_SHORT)[index] ?? '';
}

/** «YYYY-MM-DD» в поясе салона — формат, который ждёт API. */
export function toIsoDate(iso: string | Date): string {
  const { year, month, day } = parts(iso);
  return `${year}-${pad(month)}-${pad(day)}`;
}

/** Сегодня в поясе салона. */
export function todayIso(): string {
  return toIsoDate(new Date());
}

export function addDaysIso(isoDate: string, days: number): string {
  const [year, month, day] = isoDate.split('-').map(Number);
  const date = new Date(Date.UTC(year ?? 0, (month ?? 1) - 1, (day ?? 1) + days));
  return `${date.getUTCFullYear()}-${pad(date.getUTCMonth() + 1)}-${pad(date.getUTCDate())}`;
}

/** «9 000 ₸». Цена приходит строкой: numeric(10,2) нельзя класть во float. */
export function formatMoney(value: string | number): string {
  const amount = typeof value === 'string' ? Number(value) : value;
  if (Number.isNaN(amount)) return '—';
  return `${new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 }).format(amount)} ₸`;
}

/** «1 ч 30 мин», «45 мин». */
export function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours === 0) return `${rest} мин`;
  if (rest === 0) return `${hours} ч`;
  return `${hours} ч ${rest} мин`;
}

/** Склонение: 1 запись, 2 записи, 5 записей. */
export function plural(count: number, one: string, few: string, many: string): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}
