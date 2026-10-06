import { useSearchParams } from 'react-router-dom';

import { useCatalog } from '@/api/queries';
import { Skeleton } from '@/components/ui/Skeleton';
import { BookingWizard } from '@/features/booking/BookingWizard';

export function BookingPage() {
  const [searchParams] = useSearchParams();
  const serviceId = Number(searchParams.get('service')) || null;
  const { data, isPending } = useCatalog();

  // Услугу могли передать ссылкой из каталога — тогда первый шаг пропускаем.
  const preselected =
    serviceId === null
      ? null
      : ((data ?? [])
          .flatMap((category) => category.services)
          .find((s) => s.id === serviceId) ?? null);

  return (
    <div className="mx-auto max-w-2xl space-y-8">
      <header>
        <h1 className="text-2xl font-semibold text-sand-900">Запись онлайн</h1>
        <p className="mt-1.5 text-sand-600">Четыре шага — и вы записаны.</p>
      </header>

      {serviceId !== null && isPending ? (
        <Skeleton className="h-96" />
      ) : (
        <BookingWizard initialService={preselected} />
      )}
    </div>
  );
}
