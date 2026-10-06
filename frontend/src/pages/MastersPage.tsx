import { Link } from 'react-router-dom';

import { useMasters } from '@/api/queries';
import { Avatar } from '@/components/ui/Avatar';
import { EmptyState } from '@/components/ui/EmptyState';
import { RowsSkeleton } from '@/components/ui/Skeleton';
import { plural } from '@/lib/format';

export function MastersPage() {
  const { data, isPending, isError } = useMasters();
  const masters = data?.items ?? [];

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-sand-900">Мастера</h1>
        <p className="mt-1.5 text-sand-600">Выберите, у кого хотите записаться.</p>
      </header>

      {isPending ? (
        <RowsSkeleton rows={4} />
      ) : isError || masters.length === 0 ? (
        <EmptyState title="Пока нет ни одного мастера" />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {masters.map((master) => (
            <Link
              key={master.id}
              to={`/masters/${master.id}`}
              className="flex items-start gap-4 rounded-2xl border border-sand-200 bg-white p-5 transition-colors hover:border-clay-300 hover:bg-clay-50/40"
            >
              <Avatar name={master.full_name} photoUrl={master.photo_url} />
              <div className="min-w-0">
                <h2 className="font-medium text-sand-900">{master.full_name}</h2>
                {master.bio && (
                  <p className="mt-1 line-clamp-2 text-sm text-sand-600">{master.bio}</p>
                )}
                <p className="mt-2 text-sm text-sand-500">
                  {master.services.length}{' '}
                  {plural(master.services.length, 'услуга', 'услуги', 'услуг')}
                </p>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
