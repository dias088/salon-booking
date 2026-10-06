import { Link } from 'react-router-dom';

import { Button } from '@/components/ui/Button';
import { EmptyState } from '@/components/ui/EmptyState';

export function NotFoundPage() {
  return (
    <EmptyState
      icon="404"
      title="Такой страницы нет"
      description="Возможно, ссылка устарела."
      action={
        <Link to="/">
          <Button>На главную</Button>
        </Link>
      }
    />
  );
}
