"""Демо-данные для локального запуска и скриншотов.

Запуск:  python -m app.seed   (или make seed)

Скрипт полностью пересоздаёт содержимое: сначала TRUNCATE, потом вставка,
поэтому его безопасно вызывать сколько угодно раз. Данные детерминированы
(фиксированный seed у random), чтобы скриншоты и демо не «плыли» между
запусками.

Что получается:
  * 1 администратор, 4 мастера с разными графиками, 2 клиента
  * 3 категории и 12 услуг
  * один отпуск у мастера-колориста
  * визиты за полгода назад и на две недели вперёд — чтобы и график
    выручки, и «Мои записи», и админ-календарь были заполнены
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.db.models import (
    Appointment,
    AppointmentStatus,
    Master,
    MasterService,
    Service,
    ServiceCategory,
    TimeOff,
    User,
    UserRole,
    WorkingHours,
)
from app.db.session import SessionFactory, engine

TZ = settings.salon_timezone
RNG = random.Random(20261004)

ADMIN_PASSWORD = "admin1234"
CLIENT_PASSWORD = "client1234"
MASTER_PASSWORD = "master1234"

#: Глубина истории. Страница статистики по умолчанию показывает полгода,
#: и если данных за часть периода нет, загрузка мастеров размазывается:
#: ёмкость считается за все месяцы, а визиты есть только за часть.
HISTORY_MONTHS = 6

#: Доля свободных слотов, которые превращаются в визиты. Задаём именно долю,
#: а не количество: тогда загрузка мастеров остаётся правдоподобной при любой
#: глубине истории. 0.5 даёт примерно 30-40% — как в живом салоне.
PAST_FILL_RATIO = 0.5

#: Будущие визиты: чтобы в «Моих записях» было что отменять, а в админ-календаре
#: на ближайшие дни были блоки, а не пустая сетка.
FUTURE_APPOINTMENTS_TARGET = 40

MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY = range(7)

Interval = tuple[time, time]
Schedule = dict[int, list[Interval]]


@dataclass(frozen=True)
class ServiceSeed:
    name: str
    duration_min: int
    price: int
    description: str


@dataclass(frozen=True)
class CategorySeed:
    name: str
    sort_order: int
    services: list[ServiceSeed]


@dataclass(frozen=True)
class MasterSeed:
    full_name: str
    email: str
    phone: str
    bio: str
    schedule: Schedule
    service_names: list[str]
    #: service_name -> (price_override, duration_min_override)
    overrides: dict[str, tuple[int | None, int | None]] = field(default_factory=dict)


CATEGORIES: list[CategorySeed] = [
    CategorySeed(
        name="Стрижки и укладки",
        sort_order=10,
        services=[
            ServiceSeed("Женская стрижка", 60, 9000, "Мытьё, стрижка, укладка феном."),
            ServiceSeed("Мужская стрижка", 45, 6000, "Классическая или машинкой, с окантовкой."),
            ServiceSeed("Детская стрижка", 30, 4500, "Для детей до 12 лет, спокойно и быстро."),
            ServiceSeed(
                "Укладка и локоны", 60, 8000, "Укладка на выход: плойка, брашинг, фиксация."
            ),
        ],
    ),
    CategorySeed(
        name="Окрашивание",
        sort_order=20,
        services=[
            ServiceSeed("Окрашивание в один тон", 120, 22000, "Корни и полотно в один цвет."),
            ServiceSeed("Airtouch", 240, 55000, "Растяжка цвета с выдуванием коротких волос."),
            ServiceSeed("Тонирование", 90, 15000, "Освежить цвет и убрать желтизну."),
            ServiceSeed("Осветление корней", 150, 30000, "Отросшие корни + тонирование."),
        ],
    ),
    CategorySeed(
        name="Маникюр и педикюр",
        sort_order=30,
        services=[
            ServiceSeed("Классический маникюр", 60, 7000, "Обработка кутикулы, форма, масло."),
            ServiceSeed("Маникюр с гель-лаком", 90, 11000, "Маникюр и однотонное покрытие."),
            ServiceSeed("Педикюр", 90, 13000, "Аппаратная обработка стоп и ногтей."),
            ServiceSeed("Снятие покрытия", 30, 3000, "Аккуратное снятие гель-лака."),
        ],
    ),
]

WEEKDAYS_MON_FRI = [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]

MASTERS: list[MasterSeed] = [
    MasterSeed(
        full_name="Айгерим Нурланова",
        email="aigerim@salon.dev",
        phone="+7 701 100 10 01",
        bio="Парикмахер-стилист, 8 лет в профессии. Женские и детские стрижки, укладки.",
        # Пн-Пт с обедом 14:00-15:00 — два интервала в один день недели.
        schedule={
            d: [(time(10, 0), time(14, 0)), (time(15, 0), time(19, 0))] for d in WEEKDAYS_MON_FRI
        },
        service_names=[
            "Женская стрижка",
            "Мужская стрижка",
            "Детская стрижка",
            "Укладка и локоны",
        ],
        overrides={"Женская стрижка": (10500, None)},
    ),
    MasterSeed(
        full_name="Дария Ким",
        email="dariya@salon.dev",
        phone="+7 701 100 10 02",
        bio="Колорист. Airtouch, сложные растяжки, работа с блондом.",
        # Вт-Сб без обеда, длинная смена под долгие окрашивания.
        schedule={
            d: [(time(11, 0), time(20, 0))]
            for d in (TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY)
        },
        service_names=[
            "Окрашивание в один тон",
            "Airtouch",
            "Тонирование",
            "Осветление корней",
            "Укладка и локоны",
        ],
        overrides={"Airtouch": (62000, None)},
    ),
    MasterSeed(
        full_name="Мадина Сапарова",
        email="madina@salon.dev",
        phone="+7 701 100 10 03",
        bio="Мастер маникюра и педикюра. Аппаратная техника, укрепление.",
        schedule={
            MONDAY: [(time(9, 0), time(13, 0)), (time(14, 0), time(18, 0))],
            WEDNESDAY: [(time(9, 0), time(13, 0)), (time(14, 0), time(18, 0))],
            FRIDAY: [(time(9, 0), time(13, 0)), (time(14, 0), time(18, 0))],
            SATURDAY: [(time(10, 0), time(16, 0))],
        },
        service_names=[
            "Классический маникюр",
            "Маникюр с гель-лаком",
            "Педикюр",
            "Снятие покрытия",
        ],
    ),
    MasterSeed(
        full_name="Арман Токтаров",
        email="arman@salon.dev",
        phone="+7 701 100 10 04",
        bio="Барбер. Мужские стрижки, бороды, работа с машинкой.",
        # Со среды по воскресенье — закрывает выходные, когда остальные отдыхают.
        schedule={
            d: [(time(12, 0), time(21, 0))] for d in (WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY)
        },
        service_names=["Мужская стрижка", "Детская стрижка"],
        # Работает быстрее: 30 минут вместо 45.
        overrides={"Мужская стрижка": (7000, 30)},
    ),
]

CLIENTS: list[tuple[str, str, str]] = [
    ("client@salon.dev", "Алия Жумабаева", "+7 707 555 00 11"),
    ("client2@salon.dev", "Ержан Сериков", "+7 707 555 00 22"),
]

#: Таблицы в порядке, безопасном для TRUNCATE ... CASCADE.
TABLES_TO_WIPE = (
    "appointments",
    "master_services",
    "working_hours",
    "time_off",
    "masters",
    "services",
    "service_categories",
    "refresh_tokens",
    "users",
)


def local_dt(day: date, moment: time) -> datetime:
    """Локальное время салона -> aware datetime (в БД уйдёт как timestamptz)."""
    return datetime.combine(day, moment, tzinfo=TZ)


def month_start(day: date) -> date:
    return day.replace(day=1)


def history_start(day: date) -> date:
    """Первое число месяца, с которого начинается демо-история."""
    first = month_start(day)
    for _ in range(HISTORY_MONTHS - 1):
        first = month_start(first - timedelta(days=1))
    return first


def vacation_window(today: date) -> tuple[datetime, datetime]:
    """Отпуск колориста: через 3 дня, на неделю. Одно место на весь сид."""
    return (
        local_dt(today + timedelta(days=3), time(0, 0)),
        local_dt(today + timedelta(days=10), time(0, 0)),
    )


async def wipe(session: AsyncSession) -> None:
    await session.execute(text(f"TRUNCATE {', '.join(TABLES_TO_WIPE)} RESTART IDENTITY CASCADE"))


async def create_catalog(session: AsyncSession) -> dict[str, Service]:
    services: dict[str, Service] = {}
    for category_seed in CATEGORIES:
        category = ServiceCategory(name=category_seed.name, sort_order=category_seed.sort_order)
        session.add(category)
        for service_seed in category_seed.services:
            service = Service(
                category=category,
                name=service_seed.name,
                description=service_seed.description,
                duration_min=service_seed.duration_min,
                price=Decimal(service_seed.price),
                is_active=True,
            )
            session.add(service)
            services[service_seed.name] = service
    await session.flush()
    return services


async def create_people(
    session: AsyncSession, services: dict[str, Service]
) -> tuple[User, list[User], list[Master]]:
    admin = User(
        email="admin@salon.dev",
        password_hash=hash_password(ADMIN_PASSWORD),
        full_name="Администратор салона",
        phone="+7 701 000 00 00",
        role=UserRole.admin,
    )
    session.add(admin)

    clients = [
        User(
            email=email,
            password_hash=hash_password(CLIENT_PASSWORD),
            full_name=full_name,
            phone=phone,
            role=UserRole.client,
        )
        for email, full_name, phone in CLIENTS
    ]
    session.add_all(clients)

    masters: list[Master] = []
    for seed in MASTERS:
        user = User(
            email=seed.email,
            password_hash=hash_password(MASTER_PASSWORD),
            full_name=seed.full_name,
            phone=seed.phone,
            role=UserRole.master,
        )
        session.add(user)
        master = Master(user=user, bio=seed.bio, photo_url=None, is_active=True)
        session.add(master)

        for weekday, intervals in seed.schedule.items():
            for start_time, end_time in intervals:
                master.working_hours.append(
                    WorkingHours(weekday=weekday, start_time=start_time, end_time=end_time)
                )

        for service_name in seed.service_names:
            price_override, duration_override = seed.overrides.get(service_name, (None, None))
            master.services.append(
                MasterService(
                    service=services[service_name],
                    price_override=None if price_override is None else Decimal(price_override),
                    duration_min_override=duration_override,
                )
            )
        masters.append(master)

    await session.flush()
    return admin, clients, masters


async def create_time_off(session: AsyncSession, masters: list[Master], today: date) -> None:
    """Один отпуск — у колориста, начинается через три дня и длится неделю.

    Нужен, чтобы в демо было видно: в эти дни мастер не предлагается вовсе,
    а алгоритм слотов возвращает пустой список.
    """
    colorist = masters[1]
    starts_at, ends_at = vacation_window(today)
    session.add(
        TimeOff(
            master_id=colorist.id,
            period=Range(starts_at, ends_at, bounds="[)"),
            reason="Отпуск",
        )
    )
    await session.flush()


def master_offers(
    seed: MasterSeed, services: dict[str, Service]
) -> list[tuple[Service, int, Decimal]]:
    """(услуга, эффективная длительность, эффективная цена) для сида визитов."""
    offers: list[tuple[Service, int, Decimal]] = []
    for name in seed.service_names:
        service = services[name]
        price_override, duration_override = seed.overrides.get(name, (None, None))
        duration = duration_override or service.duration_min
        price = Decimal(price_override) if price_override is not None else service.price
        offers.append((service, duration, price))
    return offers


@dataclass
class Candidate:
    master: Master
    service: Service
    starts_at: datetime
    ends_at: datetime
    price: Decimal


def build_candidates(
    masters: list[Master],
    services: dict[str, Service],
    day_from: date,
    day_to: date,
    vacation: tuple[datetime, datetime],
) -> list[Candidate]:
    """Непересекающиеся «возможные визиты» внутри рабочих часов мастеров.

    Идём по рабочему интервалу слева направо и либо ставим визит, либо
    сдвигаемся на полчаса. За счёт последовательного обхода два кандидата
    одного мастера пересечься не могут, поэтому любое их подмножество
    гарантированно проходит ограничение appointments_no_overlap.
    """
    candidates: list[Candidate] = []
    vacation_from, vacation_to = vacation

    for seed, master in zip(MASTERS, masters, strict=True):
        offers = master_offers(seed, services)
        day = day_from
        while day < day_to:
            for start_time, end_time in seed.schedule.get(day.weekday(), []):
                cursor = local_dt(day, start_time)
                interval_end = local_dt(day, end_time)
                while cursor < interval_end:
                    service, duration, price = offers[RNG.randrange(len(offers))]
                    ends_at = cursor + timedelta(minutes=duration)
                    if ends_at > interval_end:
                        break
                    on_vacation = cursor < vacation_to and ends_at > vacation_from
                    if not on_vacation and RNG.random() < 0.55:
                        candidates.append(
                            Candidate(
                                master=master,
                                service=service,
                                starts_at=cursor,
                                ends_at=ends_at,
                                price=price,
                            )
                        )
                        cursor = ends_at + timedelta(minutes=RNG.choice([0, 15, 30]))
                    else:
                        cursor += timedelta(minutes=30)
            day += timedelta(days=1)
    return candidates


def pick_status(candidate: Candidate, now: datetime) -> tuple[AppointmentStatus, datetime | None]:
    if candidate.ends_at < now:
        roll = RNG.random()
        if roll < 0.82:
            return AppointmentStatus.completed, None
        if roll < 0.91:
            return AppointmentStatus.no_show, None
        return AppointmentStatus.cancelled, candidate.starts_at - timedelta(
            hours=RNG.randint(3, 48)
        )
    if RNG.random() < 0.88:
        return AppointmentStatus.booked, None
    return AppointmentStatus.cancelled, now - timedelta(hours=RNG.randint(1, 72))


async def create_appointments(
    session: AsyncSession,
    masters: list[Master],
    services: dict[str, Service],
    clients: list[User],
    now: datetime,
) -> int:
    today = now.date()
    past_from = history_start(today)
    future_to = today + timedelta(days=15)
    vacation = vacation_window(today)

    candidates = build_candidates(masters, services, past_from, future_to, vacation)
    past = [c for c in candidates if c.ends_at < now]
    future = [c for c in candidates if c.ends_at >= now]

    chosen = RNG.sample(past, round(len(past) * PAST_FILL_RATIO))
    chosen += RNG.sample(future, min(FUTURE_APPOINTMENTS_TARGET, len(future)))

    comments = [None, None, None, "Пожалуйста, без фена", "Второй раз у вас", "Опоздаю на 5 минут"]

    for candidate in chosen:
        status, cancelled_at = pick_status(candidate, now)
        session.add(
            Appointment(
                client_id=clients[RNG.randrange(len(clients))].id,
                master_id=candidate.master.id,
                service_id=candidate.service.id,
                period=Range(candidate.starts_at, candidate.ends_at, bounds="[)"),
                price_at_booking=candidate.price,
                status=status,
                cancelled_at=cancelled_at,
                comment=RNG.choice(comments),
            )
        )
    await session.flush()
    return len(chosen)


async def seed() -> None:
    now = datetime.now(TZ)
    async with SessionFactory() as session:
        await wipe(session)
        services = await create_catalog(session)
        _admin, clients, masters = await create_people(session, services)
        await create_time_off(session, masters, now.date())
        created = await create_appointments(session, masters, services, clients, now)
        await session.commit()

        total_services = len((await session.execute(select(Service.id))).all())

    print("Демо-данные залиты:")
    print(f"  категории:   {len(CATEGORIES)}")
    print(f"  услуги:      {total_services}")
    print(f"  мастера:     {len(MASTERS)} (у колориста отпуск через 3 дня на неделю)")
    print(f"  клиенты:     {len(CLIENTS)}")
    print(f"  записи:      {created}")
    print()
    print("Входы:")
    print(f"  админ:   admin@salon.dev  / {ADMIN_PASSWORD}")
    print(f"  клиент:  client@salon.dev / {CLIENT_PASSWORD}")
    print(f"  мастер:  aigerim@salon.dev / {MASTER_PASSWORD}")


async def main() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
