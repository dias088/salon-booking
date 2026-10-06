import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter, Route, Routes } from 'react-router-dom';

import { Layout } from '@/components/layout/Layout';
import { ToastProvider } from '@/components/ui/Toast';
import { AuthProvider } from '@/lib/auth';
import { BookingPage } from '@/pages/BookingPage';
import { CatalogPage } from '@/pages/CatalogPage';
import { HomePage } from '@/pages/HomePage';
import { MasterPage } from '@/pages/MasterPage';
import { MastersPage } from '@/pages/MastersPage';
import { MyAppointmentsPage } from '@/pages/MyAppointmentsPage';
import { NotFoundPage } from '@/pages/NotFoundPage';

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
                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Routes>
          </AuthProvider>
        </BrowserRouter>
      </ToastProvider>
    </QueryClientProvider>
  );
}
