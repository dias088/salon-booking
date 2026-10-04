-- ===========================================================================
--  Аналитические запросы для админ-статистики.
--
--  Этот файл — единственный источник правды: backend загружает блоки из него
--  по маркерам `-- name: <id>` (см. app/services/sql_loader.py), поэтому
--  SQL нигде не дублируется и его можно просто вставить в psql.
--
--  Именованные параметры:
--    :date_from  — начало периода, date (включительно)
--    :date_to    — конец периода, date (не включается)
--    :tz         — часовой пояс салона, например 'Asia/Almaty'
--
--  В psql подставь значения вручную, например:
--    \set date_from '2026-09-01'
--  либо замени :date_from на литерал.
-- ===========================================================================


-- name: monthly_revenue
-- Выручка по месяцам: агрегаты + оконные функции.
--   SUM() OVER (ORDER BY month) — накопительная выручка с начала периода
--   LAG()  OVER (ORDER BY month) — выручка предыдущего месяца и прирост в %
-- Группировка по месяцу делается в часовом поясе салона, а не в UTC:
-- визит 1 сентября 01:00 по Алматы — это ещё 31 августа 20:00 UTC.
WITH monthly AS (
    SELECT
        date_trunc('month', lower(a.period) AT TIME ZONE :tz)::date AS month,
        count(*)                                                    AS appointments,
        sum(a.price_at_booking)                                     AS revenue
    FROM appointments a
    WHERE a.status = 'completed'
      AND lower(a.period) >= (:date_from::timestamp AT TIME ZONE :tz)
      AND lower(a.period) <  (:date_to::timestamp   AT TIME ZONE :tz)
    GROUP BY 1
)
SELECT
    month,
    appointments,
    revenue,
    sum(revenue) OVER (ORDER BY month)                      AS revenue_cumulative,
    lag(revenue) OVER (ORDER BY month)                      AS revenue_prev_month,
    round(
        100 * (revenue - lag(revenue) OVER (ORDER BY month))
            / NULLIF(lag(revenue) OVER (ORDER BY month), 0),
        1
    )                                                       AS revenue_growth_pct
FROM monthly
ORDER BY month;


-- name: top_services
-- Топ услуг по выручке. RANK() даёт общий рейтинг и рейтинг внутри категории,
-- а SUM(SUM(...)) OVER () — долю услуги в общей выручке периода.
SELECT
    s.id                                        AS service_id,
    s.name                                      AS service_name,
    sc.name                                     AS category_name,
    count(*)                                    AS appointments,
    sum(a.price_at_booking)                     AS revenue,
    round(avg(a.price_at_booking), 2)           AS avg_price,
    rank() OVER (ORDER BY sum(a.price_at_booking) DESC)                     AS revenue_rank,
    rank() OVER (PARTITION BY sc.id ORDER BY sum(a.price_at_booking) DESC)  AS rank_in_category,
    round(
        100 * sum(a.price_at_booking) / NULLIF(sum(sum(a.price_at_booking)) OVER (), 0),
        1
    )                                                                       AS revenue_share_pct
FROM appointments a
JOIN services           s  ON s.id  = a.service_id
JOIN service_categories sc ON sc.id = s.category_id
WHERE a.status = 'completed'
  AND lower(a.period) >= (:date_from::timestamp AT TIME ZONE :tz)
  AND lower(a.period) <  (:date_to::timestamp   AT TIME ZONE :tz)
GROUP BY s.id, s.name, sc.id, sc.name
ORDER BY revenue DESC;


-- name: master_utilization
-- Загрузка мастеров в процентах.
--   capacity_min — рабочие минуты по графику за период; дни, пересечённые
--                  отпуском, из ёмкости выбрасываются целиком
--   booked_min   — минуты всех неотменённых визитов
-- weekday в working_hours: 0 = понедельник, поэтому ISODOW - 1.
WITH bounds AS (
    SELECT :date_from::date AS day_from,
           :date_to::date   AS day_to,
           :tz::text        AS tz
),
calendar AS (
    SELECT g::date AS day, b.tz
    FROM bounds b,
         generate_series(b.day_from, b.day_to - 1, interval '1 day') AS g
),
capacity AS (
    SELECT
        wh.master_id,
        sum(EXTRACT(EPOCH FROM (wh.end_time - wh.start_time)) / 60)::numeric AS capacity_min
    FROM calendar c
    JOIN working_hours wh ON wh.weekday = EXTRACT(ISODOW FROM c.day)::int - 1
    WHERE NOT EXISTS (
        SELECT 1
        FROM time_off t
        WHERE t.master_id = wh.master_id
          AND t.period && tstzrange(
                  (c.day::timestamp)       AT TIME ZONE c.tz,
                  ((c.day + 1)::timestamp) AT TIME ZONE c.tz,
                  '[)'
              )
    )
    GROUP BY wh.master_id
),
booked AS (
    SELECT
        a.master_id,
        count(*)                                                              AS appointments,
        sum(EXTRACT(EPOCH FROM (upper(a.period) - lower(a.period))) / 60)::numeric AS booked_min,
        COALESCE(sum(a.price_at_booking) FILTER (WHERE a.status = 'completed'), 0) AS revenue
    FROM appointments a, bounds b
    WHERE a.status <> 'cancelled'
      AND lower(a.period) >= (b.day_from::timestamp AT TIME ZONE b.tz)
      AND lower(a.period) <  (b.day_to::timestamp   AT TIME ZONE b.tz)
    GROUP BY a.master_id
)
SELECT
    m.id                              AS master_id,
    u.full_name                       AS master_name,
    COALESCE(c.capacity_min, 0)       AS capacity_min,
    COALESCE(bk.booked_min, 0)        AS booked_min,
    COALESCE(bk.appointments, 0)      AS appointments,
    COALESCE(bk.revenue, 0)           AS revenue,
    round(100 * COALESCE(bk.booked_min, 0) / NULLIF(c.capacity_min, 0), 1) AS utilization_pct,
    rank() OVER (
        ORDER BY COALESCE(bk.booked_min, 0) / NULLIF(c.capacity_min, 0) DESC NULLS LAST
    )                                 AS utilization_rank
FROM masters m
JOIN users u ON u.id = m.user_id
LEFT JOIN capacity c  ON c.master_id  = m.id
LEFT JOIN booked   bk ON bk.master_id = m.id
WHERE m.is_active
ORDER BY utilization_pct DESC NULLS LAST, master_name;


-- name: busiest_weekdays
-- Прямое продолжение запроса 3.5 из Assignment III: самые загруженные дни
-- недели. Отличия — время берётся из диапазона и переводится в пояс салона,
-- а доля считается оконной функцией.
SELECT
    EXTRACT(ISODOW FROM lower(a.period) AT TIME ZONE :tz)::int - 1 AS weekday,
    to_char(lower(a.period) AT TIME ZONE :tz, 'TMDay')             AS weekday_name,
    count(*)                                                       AS appointments,
    round(100 * count(*)::numeric / NULLIF(sum(count(*)) OVER (), 0), 1) AS share_pct
FROM appointments a
WHERE a.status <> 'cancelled'
  AND lower(a.period) >= (:date_from::timestamp AT TIME ZONE :tz)
  AND lower(a.period) <  (:date_to::timestamp   AT TIME ZONE :tz)
GROUP BY 1, 2
ORDER BY appointments DESC, weekday;


-- name: status_breakdown
-- Сколько записей в каком статусе за период — для верхних плашек дашборда.
SELECT
    a.status::text                                                      AS status,
    count(*)                                                            AS appointments,
    COALESCE(sum(a.price_at_booking), 0)                                AS amount,
    round(100 * count(*)::numeric / NULLIF(sum(count(*)) OVER (), 0), 1) AS share_pct
FROM appointments a
WHERE lower(a.period) >= (:date_from::timestamp AT TIME ZONE :tz)
  AND lower(a.period) <  (:date_to::timestamp   AT TIME ZONE :tz)
GROUP BY a.status
ORDER BY appointments DESC;
