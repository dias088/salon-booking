-- Assignment III — DQL & DML, переписано под базу из Assignment II
-- Таблицы: CLIENT, STYLIST, SERVICE, STATION, PRODUCT, APPOINTMENT, APPOINTMENT_SERVICE, PAYMENT
-- Выполнять по одному запросу (выделить -> F5), строго сверху вниз.

-- ===== 1. WHERE =====

-- 1.1 Дорогие услуги категорий Hair и Skin (IN + AND)
SELECT ServiceID, ServiceName, Category, Price, DurationMinutes
FROM SERVICE
WHERE Category IN ('Hair', 'Skin')
  AND Price > 80
ORDER BY Price DESC;

-- 1.2 Завершённые визиты летом 2026 (BETWEEN)
SELECT AppointmentID, ClientID, StylistID, AppointmentDate, Status
FROM APPOINTMENT
WHERE AppointmentDate BETWEEN '2026-06-01' AND '2026-08-31'
  AND Status = 'Completed'
ORDER BY AppointmentDate;

-- 1.3 Клиенты, чья фамилия начинается на W (LIKE)
SELECT ClientID, FirstName, LastName, Email
FROM CLIENT
WHERE LastName LIKE 'W%'
ORDER BY FirstName;

-- 1.4 Колористы, нанятые с 2023 года
SELECT StylistID, FirstName, LastName, Specialization, HireDate
FROM STYLIST
WHERE Specialization = 'Hair Colorist'
  AND HireDate >= '2023-01-01'
ORDER BY HireDate;

-- 1.5 Отменённые и пропущенные визиты
SELECT AppointmentID, ClientID, AppointmentDate, Status
FROM APPOINTMENT
WHERE Status IN ('Cancelled', 'No-show')
ORDER BY AppointmentDate;

-- ===== 2. STRING FUNCTIONS =====

-- 2.1 Полное имя и специализация (CONCAT, UPPER)
SELECT StylistID,
       CONCAT(FirstName, ' ', LastName) AS full_name,
       UPPER(Specialization)            AS specialization
FROM STYLIST
ORDER BY StylistID;

-- 2.2 Короткое имя и e-mail в верхнем регистре (LEFT, ||, UPPER, LOWER)
SELECT ClientID,
       LEFT(FirstName, 1) || '. ' || LastName AS short_name,
       LOWER(Email)                           AS email_lower,
       UPPER(LastName)                        AS last_name_upper
FROM CLIENT
ORDER BY ClientID;

-- 2.3 Код региона из телефона (SUBSTRING)
SELECT ClientID, FirstName, Phone,
       SUBSTRING(Phone FROM 4 FOR 3) AS area_code
FROM CLIENT
ORDER BY area_code;

-- 2.4 Длина названия и основная часть до дефиса (LENGTH, POSITION, TRIM, SPLIT_PART)
SELECT ServiceID, ServiceName,
       LENGTH(ServiceName)                    AS name_length,
       POSITION('-' IN ServiceName)           AS dash_position,
       TRIM(SPLIT_PART(ServiceName, '-', 1))  AS base_name
FROM SERVICE
WHERE ServiceName LIKE '%-%';

-- 2.5 Коды услуг для прайса (UPPER, LEFT, LPAD, REPLACE)
SELECT ServiceID,
       UPPER(LEFT(Category, 3)) || '-' || LPAD(ServiceID::TEXT, 3, '0') AS service_code,
       REPLACE(ServiceName, '''s', '') AS label,
       Price
FROM SERVICE
ORDER BY ServiceID;

-- ===== 3. DATE FUNCTIONS =====

-- 3.1 Визиты за последние 30 дней (CURRENT_DATE, INTERVAL, разница дат)
SELECT AppointmentID, ClientID, AppointmentDate, Status,
       CURRENT_DATE - AppointmentDate AS days_ago
FROM APPOINTMENT
WHERE AppointmentDate >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY AppointmentDate;

-- 3.2 Возраст клиентов (AGE, EXTRACT)
SELECT ClientID, FirstName, DateOfBirth,
       EXTRACT(YEAR FROM AGE(CURRENT_DATE, DateOfBirth)) AS age
FROM CLIENT
ORDER BY age;

-- 3.3 Выручка по месяцам (EXTRACT YEAR / MONTH)
SELECT EXTRACT(YEAR  FROM PaymentDate) AS year,
       EXTRACT(MONTH FROM PaymentDate) AS month,
       COUNT(*)    AS payments,
       SUM(Amount) AS revenue
FROM PAYMENT
GROUP BY year, month
ORDER BY year, month;

-- 3.4 Стаж стилистов (аналог DATEDIFF)
SELECT StylistID, FirstName, LastName, HireDate,
       CURRENT_DATE - HireDate                        AS days_worked,
       EXTRACT(YEAR FROM AGE(CURRENT_DATE, HireDate)) AS years_worked
FROM STYLIST
ORDER BY HireDate;

-- 3.5 Самые загруженные дни недели (EXTRACT DOW, TO_CHAR)
SELECT EXTRACT(DOW FROM AppointmentDate) AS day_no,
       TO_CHAR(AppointmentDate, 'Day')    AS day_name,
       COUNT(*)                           AS appointments
FROM APPOINTMENT
GROUP BY day_no, day_name
ORDER BY appointments DESC, day_no;

-- ===== 4. UPDATE =====

-- 4.1 Поднять цены на ногтевые услуги на 10%
UPDATE SERVICE
SET Price = Price * 1.10
WHERE Category = 'Nails'
RETURNING ServiceID, ServiceName, Price;

-- 4.2 Прошедшие записи со статусом 'Scheduled' -> 'No-show'
UPDATE APPOINTMENT
SET Status = 'No-show'
WHERE Status = 'Scheduled'
  AND AppointmentDate < CURRENT_DATE
RETURNING AppointmentID, ClientID, AppointmentDate, Status;

-- 4.3 Начислить 10 бонусных баллов за каждый завершённый визит
UPDATE CLIENT c
SET LoyaltyPoints = LoyaltyPoints + 10 * (
    SELECT COUNT(*) FROM APPOINTMENT a
    WHERE a.ClientID = c.ClientID AND a.Status = 'Completed'
)
WHERE EXISTS (
    SELECT 1 FROM APPOINTMENT a
    WHERE a.ClientID = c.ClientID AND a.Status = 'Completed'
)
RETURNING ClientID, FirstName, LastName, LoyaltyPoints;

-- 4.4 Пополнить склад: +50 к товарам, которых меньше 15 шт.
UPDATE PRODUCT
SET StockQuantity = StockQuantity + 50
WHERE StockQuantity < 15
RETURNING ProductID, ProductName, StockQuantity;

-- 4.5 Скрыть услуги, которые ни разу не заказывали
UPDATE SERVICE s
SET IsActive = FALSE
WHERE NOT EXISTS (
    SELECT 1 FROM APPOINTMENT_SERVICE aps
    WHERE aps.ServiceID = s.ServiceID
)
RETURNING ServiceID, ServiceName, IsActive;

-- ===== 5. DELETE =====

-- 5.1 Удалить платежи старше одного года
DELETE FROM PAYMENT
WHERE PaymentDate < CURRENT_DATE - INTERVAL '1 year'
RETURNING PaymentID, AppointmentID, Amount, PaymentDate;

-- 5.2 Удалить услуги из отменённых визитов
DELETE FROM APPOINTMENT_SERVICE
WHERE AppointmentID IN (
    SELECT AppointmentID FROM APPOINTMENT WHERE Status = 'Cancelled'
)
RETURNING AppointmentServiceID, AppointmentID, ServiceID;

-- 5.3 Удалить старые отменённые / пропущенные визиты (старше 6 месяцев)
--     связанные PAYMENT и APPOINTMENT_SERVICE удалятся сами (ON DELETE CASCADE)
DELETE FROM APPOINTMENT
WHERE Status IN ('Cancelled', 'No-show')
  AND AppointmentDate < CURRENT_DATE - INTERVAL '6 months'
RETURNING AppointmentID, ClientID, AppointmentDate, Status;

-- 5.4 Удалить товары, привязанные к скрытым услугам
DELETE FROM PRODUCT
WHERE ServiceID IN (SELECT ServiceID FROM SERVICE WHERE IsActive = FALSE)
RETURNING ProductID, ProductName, ServiceID;

-- 5.5 Удалить скрытые услуги, которые нигде не используются
DELETE FROM SERVICE s
WHERE s.IsActive = FALSE
  AND NOT EXISTS (SELECT 1 FROM APPOINTMENT_SERVICE aps WHERE aps.ServiceID = s.ServiceID)
  AND NOT EXISTS (SELECT 1 FROM PRODUCT p WHERE p.ServiceID = s.ServiceID)
RETURNING ServiceID, ServiceName, Price;