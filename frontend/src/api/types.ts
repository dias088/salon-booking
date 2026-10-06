/** Типы ответов API. Повторяют схемы Pydantic на бэкенде. */

export type UserRole = 'client' | 'master' | 'admin';
export type AppointmentStatus = 'booked' | 'completed' | 'cancelled' | 'no_show';

export interface User {
  id: number;
  email: string;
  full_name: string;
  phone: string;
  role: UserRole;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: User;
}

export interface Service {
  id: number;
  name: string;
  description: string | null;
  duration_min: number;
  /** numeric(10,2) приходит строкой, чтобы не терять точность. */
  price: string;
  is_active: boolean;
  category_id: number;
  category_name: string;
}

export interface CategoryWithServices {
  id: number;
  name: string;
  sort_order: number;
  services: Service[];
}

export interface Category {
  id: number;
  name: string;
  sort_order: number;
}

export interface MasterService {
  service_id: number;
  service_name: string;
  category_id: number;
  category_name: string;
  price: string;
  duration_min: number;
  has_custom_price: boolean;
  has_custom_duration: boolean;
}

export interface Master {
  id: number;
  full_name: string;
  bio: string | null;
  photo_url: string | null;
  is_active: boolean;
  services: MasterService[];
}

export interface WorkingHours {
  id: number;
  weekday: number;
  start_time: string;
  end_time: string;
}

export interface MasterDetail extends Master {
  working_hours: WorkingHours[];
}

export interface MasterSlots {
  master_id: number;
  master_name: string;
  photo_url: string | null;
  price: string;
  duration_min: number;
  slots: string[];
}

export interface AnyMasterSlot {
  starts_at: string;
  ends_at: string;
  master_ids: number[];
}

export interface Availability {
  date: string;
  service_id: number;
  service_name: string;
  timezone: string;
  masters: MasterSlots[];
  slots: AnyMasterSlot[];
}

export interface Appointment {
  id: number;
  status: AppointmentStatus;
  starts_at: string;
  ends_at: string;
  duration_min: number;
  price_at_booking: string;
  comment: string | null;
  created_at: string;
  cancelled_at: string | null;
  client_id: number;
  client_name: string;
  client_phone: string;
  master_id: number;
  master_name: string;
  service_id: number;
  service_name: string;
  category_name: string;
  can_cancel: boolean;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface TimeOff {
  id: number;
  master_id: number;
  starts_at: string;
  ends_at: string;
  reason: string | null;
}

export interface MonthlyRevenue {
  month: string;
  appointments: number;
  revenue: string;
  revenue_cumulative: string;
  revenue_prev_month: string | null;
  revenue_growth_pct: string | null;
}

export interface TopService {
  service_id: number;
  service_name: string;
  category_name: string;
  appointments: number;
  revenue: string;
  avg_price: string;
  revenue_rank: number;
  rank_in_category: number;
  revenue_share_pct: string | null;
}

export interface MasterUtilization {
  master_id: number;
  master_name: string;
  capacity_min: string;
  booked_min: string;
  appointments: number;
  revenue: string;
  utilization_pct: string | null;
  utilization_rank: number;
}

export interface WeekdayLoad {
  weekday: number;
  weekday_name: string;
  appointments: number;
  share_pct: string | null;
}

export interface StatusBreakdown {
  status: AppointmentStatus;
  appointments: number;
  amount: string;
  share_pct: string | null;
}

export interface Stats {
  date_from: string;
  date_to: string;
  timezone: string;
  monthly_revenue: MonthlyRevenue[];
  top_services: TopService[];
  master_utilization: MasterUtilization[];
  busiest_weekdays: WeekdayLoad[];
  status_breakdown: StatusBreakdown[];
}
