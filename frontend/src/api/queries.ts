import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api';
import type {
  Appointment,
  Availability,
  CategoryWithServices,
  Master,
  MasterDetail,
  Page,
} from '@/api/types';

/** Ключи кэша в одном месте: иначе инвалидация расходится с запросами. */
export const keys = {
  catalog: ['catalog'] as const,
  masters: (serviceId?: number) => ['masters', serviceId ?? null] as const,
  master: (id: number) => ['master', id] as const,
  availability: (serviceId: number, date: string, masterId?: number | null) =>
    ['availability', serviceId, date, masterId ?? null] as const,
  myAppointments: (scope: string) => ['appointments', 'my', scope] as const,
};

export function useCatalog() {
  return useQuery({
    queryKey: keys.catalog,
    queryFn: () => api.get<CategoryWithServices[]>('/api/services/categories'),
    // Каталог меняется раз в месяц — незачем ходить за ним на каждом экране.
    staleTime: 5 * 60 * 1000,
  });
}

export function useMasters(serviceId?: number) {
  return useQuery({
    queryKey: keys.masters(serviceId),
    queryFn: () => api.get<Page<Master>>('/api/masters', { service_id: serviceId, size: 100 }),
    staleTime: 5 * 60 * 1000,
  });
}

export function useMaster(masterId: number) {
  return useQuery({
    queryKey: keys.master(masterId),
    queryFn: () => api.get<MasterDetail>(`/api/masters/${masterId}`),
  });
}

export function useAvailability(
  serviceId: number | null,
  date: string,
  masterId?: number | null,
) {
  return useQuery({
    queryKey: keys.availability(serviceId ?? 0, date, masterId),
    queryFn: () =>
      api.get<Availability>('/api/availability', {
        service_id: serviceId!,
        date,
        master_id: masterId ?? undefined,
      }),
    enabled: serviceId !== null,
    // Слоты устаревают быстро: пока клиент думает, их занимают другие.
    staleTime: 15 * 1000,
    refetchOnWindowFocus: true,
  });
}

export interface CreateAppointmentInput {
  service_id: number;
  master_id: number;
  starts_at: string;
  comment?: string | null;
}

export function useCreateAppointment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateAppointmentInput) =>
      api.post<Appointment>('/api/appointments', input),
    onSettled: () => {
      // И при успехе, и при 409 сетка слотов устарела — перезапрашиваем.
      void queryClient.invalidateQueries({ queryKey: ['availability'] });
      void queryClient.invalidateQueries({ queryKey: ['appointments'] });
    },
  });
}

export function useMyAppointments(scope: 'upcoming' | 'past' | 'all') {
  return useQuery({
    queryKey: keys.myAppointments(scope),
    queryFn: () => api.get<Page<Appointment>>('/api/appointments/my', { scope, size: 100 }),
  });
}

export function useCancelAppointment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.post<Appointment>(`/api/appointments/${id}/cancel`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['appointments'] });
      void queryClient.invalidateQueries({ queryKey: ['availability'] });
    },
  });
}
