"""Поиск свободных слотов — чистые функции.

Модуль намеренно ничего не знает ни о базе, ни о текущем времени: всё
приходит аргументами. Поэтому вся логика («помещается ли услуга до конца
смены», «обед», «отпуск», «записи впритык») проверяется юнит-тестами без
поднятия PostgreSQL, а запросы к БД живут отдельно, в queries.py.

Все интервалы — полуоткрытые [start, end), как tstzrange в базе. Благодаря
этому визит 11:00-12:00 и визит 12:00-13:00 не считаются пересекающимися,
и запись «впритык» разрешена и в коде, и в БД одинаково.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True, slots=True, order=True)
class Interval:
    """Полуоткрытый интервал времени [start, end)."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.end <= self.start:
            raise ValueError(f"Пустой или обратный интервал: {self.start} .. {self.end}")

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    def overlaps(self, other: Interval) -> bool:
        return self.start < other.end and other.start < self.end

    def contains(self, other: Interval) -> bool:
        return self.start <= other.start and other.end <= self.end


def merge_intervals(intervals: Iterable[Interval]) -> list[Interval]:
    """Склеивает пересекающиеся и соприкасающиеся интервалы.

    Нужно, чтобы отпуск, перекрывающий записи, не проверялся дважды,
    и чтобы поиск свободного времени шёл по одному отсортированному списку.
    """
    ordered = sorted(intervals)
    if not ordered:
        return []

    merged = [ordered[0]]
    for current in ordered[1:]:
        last = merged[-1]
        if current.start <= last.end:
            # Соприкасающиеся ([10,11) и [11,12)) тоже объединяем: для занятого
            # времени это один непрерывный блок.
            merged[-1] = Interval(last.start, max(last.end, current.end))
        else:
            merged.append(current)
    return merged


def subtract(base: Interval, holes: Sequence[Interval]) -> list[Interval]:
    """Вырезает из интервала занятые куски. Возвращает свободные остатки."""
    free: list[Interval] = []
    cursor = base.start
    for hole in merge_intervals(holes):
        if hole.end <= base.start or hole.start >= base.end:
            continue
        if hole.start > cursor:
            free.append(Interval(cursor, hole.start))
        cursor = max(cursor, hole.end)
        if cursor >= base.end:
            return free
    if cursor < base.end:
        free.append(Interval(cursor, base.end))
    return free


def align_up(moment: datetime, step: timedelta, anchor: datetime) -> datetime:
    """Округляет момент вверх до ближайшего узла сетки, начинающейся в anchor."""
    if moment <= anchor:
        return anchor
    elapsed = moment - anchor
    steps = -(-elapsed // step)  # деление с округлением вверх
    return anchor + steps * step


def free_slots(
    *,
    work_intervals: Sequence[Interval],
    busy: Sequence[Interval],
    duration: timedelta,
    step: timedelta,
    not_before: datetime,
) -> list[datetime]:
    """Начала слотов, в которые услуга целиком помещается в рабочее время.

    :param work_intervals: рабочие интервалы мастера за день. Их может быть
        несколько — так выражается обед: [10:00,14:00) и [15:00,19:00).
    :param busy: занятое время: активные записи и периоды отсутствия.
    :param duration: длительность услуги у этого мастера.
    :param step: шаг сетки, обычно 15 минут.
    :param not_before: раньше этого момента слоты не предлагаются
        (это «сейчас плюс минимальный запас до начала»).

    Сетка привязана к началу каждого рабочего интервала, а не к полуночи:
    смена с 10:30 должна начинаться слотом 10:30, а не 10:45.
    """
    if duration <= timedelta(0):
        raise ValueError("Длительность услуги должна быть положительной")
    if step <= timedelta(0):
        raise ValueError("Шаг сетки должен быть положительным")

    occupied = merge_intervals(busy)
    slots: list[datetime] = []

    for work in sorted(work_intervals):
        # Внутри рабочего интервала считаем по сетке от его начала,
        # но пропускаем прошедшее время одним прыжком.
        cursor = align_up(max(work.start, not_before), step, anchor=work.start)

        while cursor + duration <= work.end:
            candidate = Interval(cursor, cursor + duration)
            blocker = _first_overlap(candidate, occupied)
            if blocker is None:
                slots.append(cursor)
                cursor += step
            else:
                # Перепрыгиваем занятый блок целиком: все промежуточные узлы
                # сетки всё равно пересеклись бы с ним.
                cursor = align_up(blocker.end, step, anchor=work.start)

    return slots


def _first_overlap(candidate: Interval, occupied: Sequence[Interval]) -> Interval | None:
    for interval in occupied:
        if interval.start >= candidate.end:
            # occupied отсортирован, дальше только более поздние интервалы.
            return None
        if interval.overlaps(candidate):
            return interval
    return None
