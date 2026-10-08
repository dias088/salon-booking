import { Link } from 'react-router-dom';

import { useCatalog } from '@/api/queries';
import { Button } from '@/components/ui/Button';
import { ServiceCardSkeleton } from '@/components/ui/Skeleton';
import { formatDuration, formatMoney } from '@/lib/format';

/** Короткие обещания под кнопками. Раньше это были три пустоватые карточки. */
const PROMISES = [
  'Свободные окна в реальном времени',
  'Любой свободный мастер',
  'Отмена онлайн за 2 часа',
];

export function HomePage() {
  const { data, isPending } = useCatalog();
  const popular = (data ?? []).flatMap((category) => category.services).slice(0, 4);

  return (
    <div className="space-y-16 sm:space-y-20">
      {/*
        Герой без рамки и без карточки. Раньше он был коробкой внутри страницы
        и читался как заглушка; теперь это сама страница, а глубину даёт
        мягкое тёплое пятно за текстом.
      */}
      {/*
        overflow-x-clip обязателен: декоративное пятно шире вьюпорта и без
        обрезки растягивает страницу горизонтально на телефоне.
        Именно clip, а не hidden — вертикально пятно должно выходить вверх.
      */}
      <section className="relative isolate overflow-x-clip pt-4 sm:pt-10">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-24 left-1/2 -z-10 h-[22rem] w-[48rem] max-w-none -translate-x-1/2 rounded-full bg-clay-100/50 blur-3xl"
        />

        <p className="text-sm font-medium tracking-wide text-clay-700 uppercase">
          Алматы · ежедневно 9:00–21:00
        </p>

        <h1 className="display mt-4 max-w-2xl text-4xl leading-[1.05] sm:text-5xl lg:text-6xl">
          Запишитесь в салон
          <br />
          <span className="text-clay-600">за минуту</span>
        </h1>

        <p className="mt-5 max-w-lg text-lg leading-relaxed text-sand-600">
          Выберите услугу, мастера и удобное время. Занятые окна не показываем вовсе — то, что
          видно в сетке, точно свободно.
        </p>

        <div className="mt-8 flex flex-wrap items-center gap-3">
          <Link to="/booking">
            <Button size="lg">Записаться онлайн</Button>
          </Link>
          <Link to="/services">
            <Button size="lg" variant="secondary">
              Смотреть услуги
            </Button>
          </Link>
        </div>

        <ul className="mt-10 flex flex-wrap gap-x-6 gap-y-2.5 text-sm text-sand-600">
          {PROMISES.map((promise) => (
            <li key={promise} className="flex items-center gap-2">
              <CheckIcon />
              {promise}
            </li>
          ))}
        </ul>
      </section>

      <section>
        <div className="mb-6 flex items-baseline justify-between gap-4">
          <h2 className="display text-2xl">Популярные услуги</h2>
          <Link
            to="/services"
            className="group text-sm font-medium text-clay-700 transition-colors hover:text-clay-800"
          >
            Весь каталог
            <span className="ml-1 inline-block transition-transform group-hover:translate-x-0.5">
              →
            </span>
          </Link>
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {isPending
            ? Array.from({ length: 4 }, (_, index) => <ServiceCardSkeleton key={index} />)
            : popular.map((service) => (
                <Link
                  key={service.id}
                  to={`/booking?service=${service.id}`}
                  className="surface-link group p-5"
                >
                  <div className="flex items-start justify-between gap-4">
                    <h3 className="font-medium text-sand-900 transition-colors group-hover:text-clay-800">
                      {service.name}
                    </h3>
                    <span className="tabular shrink-0 text-base font-semibold text-clay-700">
                      {formatMoney(service.price)}
                    </span>
                  </div>
                  <p className="tabular mt-2 text-sm text-sand-500">
                    {formatDuration(service.duration_min)}
                    <span className="mx-1.5 text-sand-300">·</span>
                    {service.category_name}
                  </p>
                </Link>
              ))}
        </div>
      </section>
    </div>
  );
}

function CheckIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 16 16"
      className="size-4 shrink-0 text-clay-500"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3 8.5 6.5 12 13 4.5" />
    </svg>
  );
}
