import { Link } from 'react-router-dom';

import { useCatalog } from '@/api/queries';
import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { ServiceCardSkeleton } from '@/components/ui/Skeleton';
import { formatDuration, formatMoney } from '@/lib/format';

export function CatalogPage() {
  const { data, isPending, isError } = useCatalog();

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold text-sand-900">Услуги</h1>
        <p className="mt-1.5 text-sand-600">Цены указаны за одно посещение.</p>
      </header>

      {isPending ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 6 }, (_, index) => (
            <ServiceCardSkeleton key={index} />
          ))}
        </div>
      ) : isError || !data?.length ? (
        <EmptyState title="Каталог пока пуст" description="Загляните чуть позже." />
      ) : (
        data.map((category) => (
          <section key={category.id} className="space-y-3">
            <h2 className="text-lg font-semibold text-sand-900">{category.name}</h2>
            <div className="grid gap-3 sm:grid-cols-2">
              {category.services.map((service) => (
                <article key={service.id} className="flex flex-col surface p-5">
                  <div className="flex items-start justify-between gap-3">
                    <h3 className="font-medium text-sand-900">{service.name}</h3>
                    <span className="tabular shrink-0 font-semibold text-clay-700">
                      {formatMoney(service.price)}
                    </span>
                  </div>
                  {service.description && (
                    <p className="mt-2 text-sm text-sand-600">{service.description}</p>
                  )}
                  <div className="mt-4 flex items-center justify-between gap-3 pt-1">
                    <span className="tabular text-sm text-sand-500">
                      {formatDuration(service.duration_min)}
                    </span>
                    <Link to={`/booking?service=${service.id}`}>
                      <Button size="sm" variant="secondary">
                        Записаться
                      </Button>
                    </Link>
                  </div>
                </article>
              ))}
            </div>
          </section>
        ))
      )}
    </div>
  );
}
