# Исходники из курса СУБД

Здесь лежат файлы курсового проекта **Hair Salon Management System** без
изменений — как отправная точка. Итоговая схема приложения выросла из них.

| Файл | Что это |
|---|---|
| `01_assignment2_ddl.sql` | DDL: `CLIENT, STYLIST, SERVICE, STATION, PRODUCT, APPOINTMENT, APPOINTMENT_SERVICE, PAYMENT` |
| `02_assignment2_data.sql` | Наполнение: 30 клиентов, 30 стилистов, услуги, визиты |
| `03_assignment3_dql_dml.sql` | Assignment III: WHERE, строковые и датные функции, UPDATE, DELETE |
| `04_assignment3_snake_case_variant.sql` | Вариант тех же запросов под snake_case-схему |

## Что из этого сохранено

* названия `services`, `appointments`, `price_at_booking`;
* набор статусов визита (`Scheduled/Completed/Cancelled/No-show` →
  `booked/completed/cancelled/no_show`);
* `CHECK (duration_min > 0)` и `CHECK (price >= 0)` на услугах;
* `ON DELETE RESTRICT` на справочниках, `ON DELETE CASCADE` на подчинённых;
* идея `PriceAtBooking` — цена фиксируется в момент брони;
* отчёт «самые загруженные дни недели» (запрос 3.5) дожил до
  `db/sql/reports.sql` под именем `busiest_weekdays`.

## Что изменено и почему

Разбор построчно — в докстринге миграции
[`backend/alembic/versions/0001_initial_schema.py`](../../backend/alembic/versions/0001_initial_schema.py)
и в разделе README «Схема БД».

Коротко, три главных изменения:

1. **`AppointmentDate DATE` + `AppointmentTime TIME` → `period tstzrange`.**
   Из даты и времени начала не выводится конец визита, поэтому в курсовой
   схеме вопрос «пересекаются ли две записи» нельзя было даже задать.
   С диапазоном это оператор `&&`, а значит становится возможным
   `EXCLUDE`-ограничение — ядро всего проекта.
2. **`STYLIST.Specialization VARCHAR(50)` → таблица `master_services`.**
   Специализация текстом не отвечала на вопрос «кто делает эту услугу»,
   без которого нет ни каталога, ни поиска «любой свободный мастер».
3. **`SERVICE.Category VARCHAR(30)` → справочник `service_categories`.**
   Третья нормальная форма: убрано дублирование строки в каждой услуге
   и возможность опечаток.

Плюс появились `working_hours` и `time_off`, которых в курсовой схеме не
было вообще — а без них поиск свободного времени невозможен.
