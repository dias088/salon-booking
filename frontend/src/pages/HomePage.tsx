import { Link } from 'react-router-dom';

import { useCatalog } from '@/api/queries';
import { Button } from '@/components/ui/Button';
import { ServiceCardSkeleton } from '@/components/ui/Skeleton';
import { formatDuration, formatMoney } from '@/lib/format';

export function HomePage() {
  const { data, isPending } = useCatalog();
  const popular = (data ?? []).flatMap((category) => category.services).slice(0, 4);

  return (
    <div className="space-y-14">
      <section className="rounded-2xl border border-sand-200 bg-gradient-to-br from-white to-clay-50 px-6 py-12 sm:px-12 sm:py-16">
        <h1 className="max-w-xl text-3xl font-semibold leading-tight text-sand-900 sm:text-4xl">
          Запишитесь в салон за минуту
        </h1>
        <p className="mt-4 max-w-lg text-sand-600">
          Выберите услугу, мастера и удобное время. Свободные окна показываем в реальном времени
          — занятое время просто не появится в списке.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link to="/booking">
            <Button size="lg">Записаться онлайн</Button>
          </Link>
          <Link to="/services">
            <Button size="lg" variant="secondary">
              Смотреть услуги
            </Button>
          </Link>
        </div>
      </section>

      <section>
        <div className="mb-5 flex items-baseline justify-between gap-4">
          <h2 className="text-xl font-semibold text-sand-900">Популярные услуги</h2>
          <Link to="/services" className="text-sm font-medium text-clay-700 hover:underline">
            Весь каталог →
          </Link>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {isPending
            ? Array.from({ length: 4 }, (_, index) => <ServiceCardSkeleton key={index} />)
            : popular.map((service) => (
                <Link
                  key={service.id}
                  to={`/booking?service=${service.id}`}
                  className="rounded-2xl border border-sand-200 bg-white p-5 transition-colors hover:border-clay-300 hover:bg-clay-50/40"
                >
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="font-medium text-sand-900">{service.name}</h3>
                    <span className="tabular shrink-0 font-semibold text-clay-700">
                      {formatMoney(service.price)}
                    </span>
                  </div>
                  <p className="tabular mt-2 text-sm text-sand-500">
                    {formatDuration(service.duration_min)} · {service.category_name}
                  </p>
                </Link>
              ))}
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-3">
        <Feature title="Честное расписание" text="Слот исчезает, как только его занимают." />
        <Feature title="Любой свободный мастер" text="Не важно кто — важно когда." />
        <Feature title="Отмена онлайн" text="Не позднее чем за 2 часа до визита." />
      </section>
    </div>
  );
}

function Feature({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-2xl border border-sand-200 bg-white p-5">
      <h3 className="font-medium text-sand-900">{title}</h3>
      <p className="mt-1.5 text-sm text-sand-600">{text}</p>
    </div>
  );
}
