import { type ReactNode } from 'react';
import { Link } from 'react-router-dom';

import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';
import { RowsSkeleton } from '@/components/ui/Skeleton';
import { useAuth } from '@/lib/auth';
import type { UserRole } from '@/api/types';

/**
 * Защита маршрутов на клиенте — только для удобства: настоящая проверка
 * всё равно на сервере, здесь мы просто не показываем бесполезный экран.
 */
export function RequireRole({ roles, children }: { roles: UserRole[]; children: ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) return <RowsSkeleton rows={4} />;

  if (!user || !roles.includes(user.role)) {
    return (
      <EmptyState
        title="Раздел закрыт"
        description="Войдите под учётной записью с нужными правами."
        action={
          <Link to="/">
            <Button variant="secondary">На главную</Button>
          </Link>
        }
      />
    );
  }

  return <>{children}</>;
}
