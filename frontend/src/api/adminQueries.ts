import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api';
import type {
  Appointment,
  AppointmentStatus,
  Category,
  Master,
  MasterDetail,
  Page,
  Service,
  Stats,
  TimeOff,
} from '@/api/types';

export const adminKeys = {
  day: (date: string) => ['admin', 'appointments', date] as const,
  services: ['admin', 'services'] as const,
  categories: ['admin', 'categories'] as const,
  masters: ['admin', 'masters'] as const,
  timeOff: (masterId: number) => ['admin', 'time-off', masterId] as const,
  stats: (from: string | null, to: string | null) => ['admin', 'stats', from, to] as const,
  schedule: (from: string, to: string) => ['master', 'schedule', from, to] as const,
};

export function useDayAppointments(date: string) {
  return useQuery({
    queryKey: adminKeys.day(date),
    queryFn: () => api.get<Page<Appointment>>('/api/admin/appointments', { date, size: 200 }),
  });
}

export function useAdminServices() {
  return useQuery({
    queryKey: adminKeys.services,
    queryFn: () => api.get<Page<Service>>('/api/admin/services', { size: 200 }),
  });
}

export function useAdminCategories() {
  return useQuery({
    queryKey: adminKeys.categories,
    queryFn: () => api.get<Category[]>('/api/admin/categories'),
  });
}

export function useAdminMasters() {
  return useQuery({
    queryKey: adminKeys.masters,
    queryFn: () => api.get<Page<Master>>('/api/admin/masters', { size: 200 }),
  });
}

export function useStats(dateFrom: string | null, dateTo: string | null) {
  return useQuery({
    queryKey: adminKeys.stats(dateFrom, dateTo),
    queryFn: () =>
      api.get<Stats>('/api/admin/stats', {
        date_from: dateFrom ?? undefined,
        date_to: dateTo ?? undefined,
      }),
  });
}

export interface AdminBookingInput {
  service_id: number;
  master_id: number;
  starts_at: string;
  comment?: string | null;
  client_id?: number;
  client?: { full_name: string; phone: string; email?: string };
}

export function useAdminCreateAppointment() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AdminBookingInput) =>
      api.post<Appointment>('/api/admin/appointments', input),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'appointments'] });
      void queryClient.invalidateQueries({ queryKey: ['availability'] });
    },
  });
}

export function useSetAppointmentStatus(scope: 'admin' | 'master') {
  const queryClient = useQueryClient();
  const base = scope === 'admin' ? '/api/admin/appointments' : '/api/master/appointments';
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: AppointmentStatus }) =>
      api.patch<Appointment>(`${base}/${id}/status`, { status }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin'] });
      void queryClient.invalidateQueries({ queryKey: ['master'] });
    },
  });
}

export function useMasterSchedule(dateFrom: string, dateTo: string) {
  return useQuery({
    queryKey: adminKeys.schedule(dateFrom, dateTo),
    queryFn: () =>
      api.get<Page<Appointment>>('/api/master/schedule', {
        date_from: dateFrom,
        date_to: dateTo,
        size: 200,
      }),
  });
}

export function useMasterDetail(masterId: number | null) {
  return useQuery({
    queryKey: ['admin', 'master', masterId],
    queryFn: () => api.get<MasterDetail>(`/api/masters/${masterId}`),
    enabled: masterId !== null,
  });
}

export function useTimeOff(masterId: number | null) {
  return useQuery({
    queryKey: adminKeys.timeOff(masterId ?? 0),
    queryFn: () => api.get<TimeOff[]>(`/api/admin/masters/${masterId}/time-off`),
    enabled: masterId !== null,
  });
}

export function useAddTimeOff(masterId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { starts_at: string; ends_at: string; reason?: string }) =>
      api.post<TimeOff>(`/api/admin/masters/${masterId}/time-off`, input),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.timeOff(masterId) });
      void queryClient.invalidateQueries({ queryKey: ['availability'] });
    },
  });
}

export function useDeleteTimeOff(masterId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/api/admin/masters/${masterId}/time-off/${id}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: adminKeys.timeOff(masterId) });
      void queryClient.invalidateQueries({ queryKey: ['availability'] });
    },
  });
}

export function useSaveService() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }: Partial<Service> & { id?: number }) =>
      id === undefined
        ? api.post<Service>('/api/admin/services', body)
        : api.patch<Service>(`/api/admin/services/${id}`, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'services'] });
      void queryClient.invalidateQueries({ queryKey: ['catalog'] });
    },
  });
}

export function useDeleteService() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => api.delete(`/api/admin/services/${id}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'services'] });
      void queryClient.invalidateQueries({ queryKey: ['catalog'] });
    },
  });
}
