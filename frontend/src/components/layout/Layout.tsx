import { useState } from 'react';
import { Link, NavLink, Outlet } from 'react-router-dom';

import { Button } from '@/components/ui/Button';
import { AuthDialog } from '@/features/auth/AuthDialog';
import { useAuth } from '@/lib/auth';
import { cn } from '@/lib/cn';

const NAV = [
  { to: '/services', label: 'Услуги' },
  { to: '/masters', label: 'Мастера' },
];

export function Layout() {
  const { user, logout } = useAuth();
  const [authOpen, setAuthOpen] = useState(false);

  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-30 border-b border-sand-200 bg-sand-50/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-5xl items-center gap-4 px-4">
          <Link to="/" className="font-semibold tracking-tight text-sand-900">
            Салон <span className="text-clay-600">красоты</span>
          </Link>

          <nav className="hidden gap-1 sm:flex">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    isActive ? 'text-clay-700' : 'text-sand-600 hover:text-sand-900',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2">
            {user ? (
              <>
                {user.role === 'admin' && (
                  <Link
                    to="/admin"
                    className="hidden rounded-lg px-3 py-2 text-sm font-medium text-sand-600 hover:text-sand-900 sm:block"
                  >
                    Админка
                  </Link>
                )}
                {user.role === 'master' && (
                  <Link
                    to="/master"
                    className="hidden rounded-lg px-3 py-2 text-sm font-medium text-sand-600 hover:text-sand-900 sm:block"
                  >
                    Расписание
                  </Link>
                )}
                <Link
                  to="/my"
                  className="rounded-lg px-3 py-2 text-sm font-medium text-sand-700 hover:text-sand-900"
                >
                  Мои записи
                </Link>
                <Button variant="ghost" size="sm" onClick={() => void logout()}>
                  Выйти
                </Button>
              </>
            ) : (
              <Button variant="secondary" size="sm" onClick={() => setAuthOpen(true)}>
                Войти
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">
        <Outlet />
      </main>

      <footer className="border-t border-sand-200 bg-white">
        <div className="mx-auto max-w-5xl px-4 py-8 text-sm text-sand-500">
          <p>Салон красоты · Алматы · ежедневно с 9:00 до 21:00</p>
          <p className="mt-1">
            Учебный проект.{' '}
            <a href="/docs" className="underline underline-offset-2 hover:text-sand-700">
              Документация API
            </a>
          </p>
        </div>
      </footer>

      <AuthDialog open={authOpen} onClose={() => setAuthOpen(false)} />
    </div>
  );
}
