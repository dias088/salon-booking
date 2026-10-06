import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { useStats } from '@/api/adminQueries';
import { STATUS_LABELS } from '@/components/ui/Badge';
import { Card, CardTitle } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { Skeleton } from '@/components/ui/Skeleton';
import { formatMoney, formatMonth, plural, weekdayName } from '@/lib/format';

/** Акцент палитры в hex — Recharts не понимает CSS-переменные Tailwind. */
const ACCENT = '#c96a46';
const ACCENT_SOFT = '#e8aa8d';

export function AdminStatsPage() {
  const { data, isPending, isError } = useStats(null, null);

  if (isPending) {
    return (
      <div className="space-y-5">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-80 rounded-2xl" />
        <div className="grid gap-5 lg:grid-cols-2">
          <Skeleton className="h-72 rounded-2xl" />
          <Skeleton className="h-72 rounded-2xl" />
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return <EmptyState title="Не удалось загрузить статистику" />;
  }

  const totalRevenue = data.monthly_revenue.reduce(
    (sum, month) => sum + Number(month.revenue),
    0,
  );
  const totalAppointments = data.status_breakdown.reduce(
    (sum, row) => sum + row.appointments,
    0,
  );
  const completed = data.status_breakdown.find((row) => row.status === 'completed');
  const lastMonth = data.monthly_revenue.at(-1);

  const revenueData = data.monthly_revenue.map((month) => ({
    month: formatMonth(month.month),
    revenue: Number(month.revenue),
    cumulative: Number(month.revenue_cumulative),
  }));

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-sand-900">Статистика</h1>
        <p className="mt-1.5 text-sm text-sand-600">
          Период: {formatMonth(data.date_from)} — {formatMonth(data.date_to)}, пояс{' '}
          {data.timezone}
        </p>
      </header>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Выручка за период" value={formatMoney(totalRevenue)} />
        <Stat
          label="Визитов"
          value={`${totalAppointments} ${plural(totalAppointments, 'запись', 'записи', 'записей')}`}
        />
        <Stat label="Состоялось" value={completed ? `${completed.share_pct ?? '—'}%` : '—'} />
        <Stat
          label="Последний месяц"
          value={lastMonth ? formatMoney(lastMonth.revenue) : '—'}
          hint={
            lastMonth?.revenue_growth_pct
              ? `${Number(lastMonth.revenue_growth_pct) > 0 ? '+' : ''}${lastMonth.revenue_growth_pct}% к прошлому`
              : undefined
          }
        />
      </div>

      <Card>
        <CardTitle>Выручка по месяцам</CardTitle>
        <p className="mt-1 text-sm text-sand-500">
          Столбцы — выручка месяца, подпись в подсказке — накопительный итог (
          <code className="text-xs">SUM() OVER</code>).
        </p>
        <div className="mt-5 h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={revenueData} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#efe5da" vertical={false} />
              <XAxis
                dataKey="month"
                tick={{ fill: '#7a6557', fontSize: 12 }}
                tickLine={false}
                axisLine={{ stroke: '#efe5da' }}
              />
              <YAxis
                tick={{ fill: '#7a6557', fontSize: 12 }}
                tickLine={false}
                axisLine={false}
                tickFormatter={(value: number) => `${Math.round(value / 1000)}k`}
              />
              <Tooltip
                formatter={(value, name) => [
                  formatMoney(Number(value ?? 0)),
                  name === 'revenue' ? 'Выручка' : 'Накопительно',
                ]}
                contentStyle={{
                  borderRadius: 12,
                  border: '1px solid #efe5da',
                  fontSize: 13,
                }}
              />
              <Bar dataKey="revenue" fill={ACCENT} radius={[6, 6, 0, 0]} />
              <Bar dataKey="cumulative" fill={ACCENT_SOFT} radius={[6, 6, 0, 0]} hide />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardTitle>Топ услуг по выручке</CardTitle>
          <p className="mt-1 text-sm text-sand-500">
            Ранг общий и внутри категории — оконная функция{' '}
            <code className="text-xs">RANK()</code>.
          </p>
          <ul className="mt-4 space-y-3">
            {data.top_services.slice(0, 6).map((service) => (
              <li key={service.service_id}>
                <div className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="truncate font-medium text-sand-900">
                    <span className="tabular mr-1.5 text-sand-400">
                      #{service.revenue_rank}
                    </span>
                    {service.service_name}
                  </span>
                  <span className="tabular shrink-0 text-sand-700">
                    {formatMoney(service.revenue)}
                  </span>
                </div>
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-sand-100">
                  <div
                    className="h-full rounded-full bg-clay-400"
                    style={{ width: `${service.revenue_share_pct ?? 0}%` }}
                  />
                </div>
                <p className="mt-1 text-xs text-sand-500">
                  {service.category_name} · #{service.rank_in_category} в категории ·{' '}
                  {service.revenue_share_pct ?? 0}% выручки
                </p>
              </li>
            ))}
          </ul>
        </Card>

        <Card>
          <CardTitle>Загрузка мастеров</CardTitle>
          <p className="mt-1 text-sm text-sand-500">
            Забронированные минуты к рабочим часам за вычетом отпусков.
          </p>
          <ul className="mt-4 space-y-4">
            {data.master_utilization.map((master) => (
              <li key={master.master_id}>
                <div className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="truncate font-medium text-sand-900">
                    {master.master_name}
                  </span>
                  <span className="tabular shrink-0 font-semibold text-clay-700">
                    {master.utilization_pct ?? 0}%
                  </span>
                </div>
                <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-sand-100">
                  <div
                    className="h-full rounded-full bg-clay-500"
                    style={{ width: `${Math.min(Number(master.utilization_pct ?? 0), 100)}%` }}
                  />
                </div>
                <p className="tabular mt-1 text-xs text-sand-500">
                  {master.appointments}{' '}
                  {plural(master.appointments, 'визит', 'визита', 'визитов')} ·{' '}
                  {formatMoney(master.revenue)}
                </p>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardTitle>Загруженность по дням недели</CardTitle>
          <div className="mt-5 h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={data.busiest_weekdays
                  .slice()
                  .sort((a, b) => a.weekday - b.weekday)
                  .map((row) => ({
                    day: weekdayName(row.weekday),
                    appointments: row.appointments,
                  }))}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#efe5da" vertical={false} />
                <XAxis
                  dataKey="day"
                  tick={{ fill: '#7a6557', fontSize: 12 }}
                  tickLine={false}
                  axisLine={{ stroke: '#efe5da' }}
                />
                <YAxis
                  tick={{ fill: '#7a6557', fontSize: 12 }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  formatter={(value) => [`${value ?? 0}`, 'Визитов']}
                  contentStyle={{ borderRadius: 12, border: '1px solid #efe5da', fontSize: 13 }}
                />
                <Bar dataKey="appointments" radius={[6, 6, 0, 0]}>
                  {data.busiest_weekdays.map((row) => (
                    <Cell key={row.weekday} fill={row.weekday >= 5 ? ACCENT_SOFT : ACCENT} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <CardTitle>Статусы записей</CardTitle>
          <ul className="mt-4 space-y-3">
            {data.status_breakdown.map((row) => (
              <li key={row.status} className="flex items-center justify-between gap-3 text-sm">
                <span className="text-sand-700">{STATUS_LABELS[row.status]}</span>
                <span className="tabular text-sand-900">
                  {row.appointments}{' '}
                  <span className="text-sand-400">({row.share_pct ?? 0}%)</span>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="p-4">
      <p className="text-sm text-sand-500">{label}</p>
      <p className="tabular mt-1 text-xl font-semibold text-sand-900">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-sand-500">{hint}</p>}
    </Card>
  );
}
