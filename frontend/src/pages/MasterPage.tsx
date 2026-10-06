import { Link, useParams } from 'react-router-dom';

import { useMaster } from '@/api/queries';
import { Avatar } from '@/components/ui/Avatar';
import { Button } from '@/components/ui/Button';
import { Card, CardTitle } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { RowsSkeleton, Skeleton } from '@/components/ui/Skeleton';
import { formatDuration, formatMoney, weekdayName } from '@/lib/format';

export function MasterPage() {
  const { masterId } = useParams();
  const { data, isPending, isError } = useMaster(Number(masterId));

  if (isPending) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-24" />
        <RowsSkeleton rows={3} />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <EmptyState
        title="Мастер не найден"
        action={
          <Link to="/masters">
            <Button variant="secondary">Все мастера</Button>
          </Link>
        }
      />
    );
  }

  // Несколько интервалов в один день — это обед, показываем их через запятую.
  const byWeekday = new Map<number, string[]>();
  for (const hours of data.working_hours) {
    const list = byWeekday.get(hours.weekday) ?? [];
    list.push(`${hours.start_time.slice(0, 5)}–${hours.end_time.slice(0, 5)}`);
    byWeekday.set(hours.weekday, list);
  }

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-start gap-5">
        <Avatar name={data.full_name} photoUrl={data.photo_url} className="size-20 text-lg" />
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-semibold text-sand-900">{data.full_name}</h1>
          {data.bio && <p className="mt-2 max-w-xl text-sand-600">{data.bio}</p>}
        </div>
      </header>

      <div className="grid gap-5 lg:grid-cols-[2fr_1fr]">
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-sand-900">Услуги</h2>
          {data.services.length === 0 ? (
            <EmptyState title="Услуги пока не назначены" />
          ) : (
            data.services.map((offer) => (
              <article
                key={offer.service_id}
                className="flex items-center justify-between gap-4 rounded-2xl border border-sand-200 bg-white p-4"
              >
                <div className="min-w-0">
                  <h3 className="font-medium text-sand-900">{offer.service_name}</h3>
                  <p className="tabular mt-0.5 text-sm text-sand-500">
                    {formatDuration(offer.duration_min)} · {offer.category_name}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <span className="tabular font-semibold text-clay-700">
                    {formatMoney(offer.price)}
                  </span>
                  <Link
                    to={`/booking?service=${offer.service_id}&master=${data.id}`}
                    className="hidden sm:block"
                  >
                    <Button size="sm" variant="secondary">
                      Записаться
                    </Button>
                  </Link>
                </div>
              </article>
            ))
          )}
        </section>

        <Card className="h-fit">
          <CardTitle>График работы</CardTitle>
          <dl className="mt-4 space-y-2 text-sm">
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
      </div>
    </div>
  );
}
