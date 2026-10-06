import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Suspense, lazy } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { Layout } from '@/components/layout/Layout';
import { RowsSkeleton } from '@/components/ui/Skeleton';
import { ToastProvider } from '@/components/ui/Toast';
import { AuthProvider } from '@/lib/auth';
import { BookingPage } from '@/pages/BookingPage';
import { CatalogPage } from '@/pages/CatalogPage';
import { HomePage } from '@/pages/HomePage';
import { MasterPage } from '@/pages/MasterPage';
import { MastersPage } from '@/pages/MastersPage';
import { MyAppointmentsPage } from '@/pages/MyAppointmentsPage';
import { NotFoundPage } from '@/pages/NotFoundPage';

// Админка и кабинет мастера грузятся отдельным чанком: вместе с ними
// в бандл попадает Recharts (~400 КБ), а клиентская часть делалась
// в первую очередь для телефона и платить за это не должна.
const AdminLayout = lazy(() =>
  import('@/pages/admin/AdminLayout').then((m) => ({ default: m.AdminLayout })),
);
const AdminCalendarPage = lazy(() =>
  import('@/pages/admin/AdminCalendarPage').then((m) => ({ default: m.AdminCalendarPage })),
);
const AdminServicesPage = lazy(() =>
  import('@/pages/admin/AdminServicesPage').then((m) => ({ default: m.AdminServicesPage })),
);
const AdminMastersPage = lazy(() =>
  import('@/pages/admin/AdminMastersPage').then((m) => ({ default: m.AdminMastersPage })),
);
const AdminStatsPage = lazy(() =>
  import('@/pages/admin/AdminStatsPage').then((m) => ({ default: m.AdminStatsPage })),
);
const MasterSchedulePage = lazy(() =>
  import('@/pages/master/MasterSchedulePage').then((m) => ({
    default: m.MasterSchedulePage,
  })),
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        {/* Включаем поведение v7 заранее: иначе React Router пишет
            предупреждения в консоль на каждой загрузке. */}
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <AuthProvider>
            <Routes>
              <Route element={<Layout />}>
                <Route index element={<HomePage />} />
                <Route path="services" element={<CatalogPage />} />
                <Route path="masters" element={<MastersPage />} />
                <Route path="masters/:masterId" element={<MasterPage />} />
                <Route path="booking" element={<BookingPage />} />
                <Route path="my" element={<MyAppointmentsPage />} />

                <Route
                  path="admin"
                  element={
                    <Suspense fallback={<RowsSkeleton rows={4} />}>
                      <AdminLayout />
                    </Suspense>
                  }
                >
                  <Route index element={<AdminCalendarPage />} />
                  <Route path="services" element={<AdminServicesPage />} />
                  <Route path="masters" element={<AdminMastersPage />} />
                  <Route path="stats" element={<AdminStatsPage />} />
                </Route>

                <Route
                  path="master"
                  element={
                    <Suspense fallback={<RowsSkeleton rows={4} />}>
                      <MasterSchedulePage />
                    </Suspense>
                  }
                />

                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Routes>
          </AuthProvider>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}
