import { NavLink, Outlet } from 'react-router-dom';

import { RequireRole } from '@/components/RequireRole';
import { cn } from '@/lib/cn';

const TABS = [
  { to: '/admin', label: 'Календарь', end: true },
  { to: '/admin/services', label: 'Услуги' },
  { to: '/admin/masters', label: 'Мастера' },
  { to: '/admin/stats', label: 'Статистика' },
];

export function AdminLayout() {
  return (
    <RequireRole roles={['admin']}>
      <div className="space-y-6">
        <nav className="-mx-4 flex gap-2 overflow-x-auto px-4 sm:mx-0 sm:px-0">
          {TABS.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              end={tab.end}
              className={({ isActive }) =>
                cn(
                  'shrink-0 rounded-full border px-4 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'border-clay-500 bg-clay-500 text-white'
                    : 'border-sand-300 bg-white text-sand-700 hover:bg-sand-100',
                )
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
        <Outlet />
      </div>
    </RequireRole>
  );
}
