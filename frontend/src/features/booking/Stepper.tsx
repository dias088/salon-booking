import { cn } from '@/lib/cn';

export const STEP_TITLES = ['Услуга', 'Мастер', 'Время', 'Подтверждение'];

export function Stepper({
  current,
  onGoTo,
}: {
  current: number;
  /** Назад можно вернуться кликом, вперёд — только пройдя шаг. */
  onGoTo: (step: number) => void;
}) {
  return (
    <ol className="flex items-center gap-1.5 sm:gap-3">
      {STEP_TITLES.map((title, index) => {
        const done = index < current;
        const active = index === current;
        return (
          <li key={title} className="flex flex-1 items-center gap-1.5 sm:gap-3">
            <button
              type="button"
              onClick={() => done && onGoTo(index)}
              disabled={!done}
              aria-current={active ? 'step' : undefined}
              className={cn(
                'flex min-w-0 flex-1 flex-col gap-1.5 text-left',
                done && 'cursor-pointer',
              )}
            >
              <span
                className={cn(
                  'h-1 rounded-full transition-colors',
                  active || done ? 'bg-clay-500' : 'bg-sand-200',
                )}
              />
              <span
                className={cn(
                  'truncate text-xs font-medium sm:text-sm',
                  active ? 'text-clay-700' : done ? 'text-sand-600' : 'text-sand-400',
                )}
              >
                <span className="tabular">{index + 1}.</span> {title}
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
