import { Button } from '@/components/ui/Button';
import { addDaysIso, formatDateWithWeekday, todayIso } from '@/lib/format';

/** Переключатель дня: «вчера / сегодня / завтра» одной строкой. */
export function DayPicker({
  value,
  onChange,
}: {
  value: string;
  onChange: (date: string) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button variant="secondary" size="sm" onClick={() => onChange(addDaysIso(value, -1))}>
        ←
      </Button>
      <input
        type="date"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 rounded-lg border border-sand-300 bg-white px-3 text-sm text-sand-900"
        aria-label="Дата"
      />
      <Button variant="secondary" size="sm" onClick={() => onChange(addDaysIso(value, 1))}>
        →
      </Button>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => onChange(todayIso())}
        disabled={value === todayIso()}
      >
        Сегодня
      </Button>
      <span className="ml-1 text-sm text-sand-600">
        {formatDateWithWeekday(`${value}T12:00:00`)}
      </span>
    </div>
  );
}
