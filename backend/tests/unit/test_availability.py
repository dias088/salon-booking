"""Юнит-тесты алгоритма слотов. Без базы и без системного времени."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.services.availability import (
    Interval,
    align_up,
    free_slots,
    merge_intervals,
    subtract,
)

TZ = ZoneInfo("Asia/Almaty")
DAY = datetime(2026, 10, 12, tzinfo=TZ)  # понедельник
STEP = timedelta(minutes=15)
#: Заведомо раньше рабочего дня — чтобы «запас до начала» не мешал тесту.
EARLY = DAY


def at(hour: int, minute: int = 0) -> datetime:
    return DAY.replace(hour=hour, minute=minute)


def interval(start: tuple[int, int], end: tuple[int, int]) -> Interval:
    return Interval(at(*start), at(*end))


def times(slots: list[datetime]) -> list[str]:
    return [slot.strftime("%H:%M") for slot in slots]


# ---------------------------------------------------------------------------
# Строительные блоки
# ---------------------------------------------------------------------------


def test_interval_rejects_empty_and_reversed() -> None:
    with pytest.raises(ValueError, match="Пустой или обратный"):
        interval((12, 0), (12, 0))
    with pytest.raises(ValueError, match="Пустой или обратный"):
        interval((13, 0), (12, 0))


def test_adjacent_intervals_do_not_overlap() -> None:
    """Главное свойство полуоткрытых интервалов: 11:00-12:00 и 12:00-13:00 свободно стыкуются."""
    assert not interval((11, 0), (12, 0)).overlaps(interval((12, 0), (13, 0)))
    assert interval((11, 0), (12, 1)).overlaps(interval((12, 0), (13, 0)))


def test_merge_joins_touching_and_overlapping() -> None:
    merged = merge_intervals(
        [
            interval((12, 0), (13, 0)),
            interval((10, 0), (11, 0)),
            interval((11, 0), (12, 0)),  # впритык к следующему
            interval((12, 30), (14, 0)),  # пересекается
        ]
    )

    assert merged == [interval((10, 0), (14, 0))]


def test_subtract_cuts_holes_out() -> None:
    free = subtract(interval((10, 0), (18, 0)), [interval((12, 0), (13, 0))])

    assert free == [interval((10, 0), (12, 0)), interval((13, 0), (18, 0))]


def test_subtract_fully_covered_leaves_nothing() -> None:
    assert subtract(interval((10, 0), (18, 0)), [interval((9, 0), (20, 0))]) == []


def test_align_up_snaps_to_grid() -> None:
    assert align_up(at(10, 7), STEP, anchor=at(10, 0)) == at(10, 15)
    assert align_up(at(10, 15), STEP, anchor=at(10, 0)) == at(10, 15)
    # Сетка от 10:30, а не от полуночи.
    assert align_up(at(10, 31), STEP, anchor=at(10, 30)) == at(10, 45)


# ---------------------------------------------------------------------------
# Сценарии из ТЗ
# ---------------------------------------------------------------------------


def test_service_must_fit_before_end_of_shift() -> None:
    """Граница рабочего дня: часовая услуга при смене до 18:00 заканчивается слотом 17:00."""
    slots = free_slots(
        work_intervals=[interval((16, 0), (18, 0))],
        busy=[],
        duration=timedelta(minutes=60),
        step=STEP,
        not_before=EARLY,
    )

    assert times(slots) == ["16:00", "16:15", "16:30", "16:45", "17:00"]


def test_long_service_does_not_fit_at_all() -> None:
    slots = free_slots(
        work_intervals=[interval((10, 0), (11, 0))],
        busy=[],
        duration=timedelta(minutes=90),
        step=STEP,
        not_before=EARLY,
    )

    assert slots == []


def test_lunch_break_splits_the_day() -> None:
    """Обед: два интервала 10-14 и 15-19. Часовая услуга не может начаться в 13:30."""
    slots = free_slots(
        work_intervals=[interval((10, 0), (14, 0)), interval((15, 0), (19, 0))],
        busy=[],
        duration=timedelta(minutes=60),
        step=STEP,
        not_before=EARLY,
    )

    assert "13:00" in times(slots), "последний слот до обеда"
    assert "13:15" not in times(slots), "услуга вылезла бы за начало обеда"
    assert "14:00" not in times(slots), "обед не рабочее время"
    assert "15:00" in times(slots), "смена после обеда начинается сразу"
    assert times(slots)[-1] == "18:00"


def test_vacation_covering_the_day_leaves_no_slots() -> None:
    slots = free_slots(
        work_intervals=[interval((10, 0), (19, 0))],
        busy=[Interval(DAY - timedelta(days=2), DAY + timedelta(days=5))],
        duration=timedelta(minutes=30),
        step=STEP,
        not_before=EARLY,
    )

    assert slots == []


def test_booking_fits_exactly_between_two_appointments() -> None:
    """Записи впритык: между 11:00-12:00 и 13:00-14:00 ровно один часовой слот в 12:00."""
    slots = free_slots(
        work_intervals=[interval((10, 0), (18, 0))],
        busy=[interval((11, 0), (12, 0)), interval((13, 0), (14, 0))],
        duration=timedelta(minutes=60),
        step=STEP,
        not_before=EARLY,
    )

    assert "12:00" in times(slots)
    assert "11:00" not in times(slots)
    assert "12:15" not in times(slots), "услуга наехала бы на запись в 13:00"
    assert "14:00" in times(slots)


def test_gap_too_small_for_the_service() -> None:
    slots = free_slots(
        work_intervals=[interval((10, 0), (18, 0))],
        busy=[interval((11, 0), (12, 0)), interval((12, 30), (14, 0))],
        duration=timedelta(minutes=60),
        step=STEP,
        not_before=EARLY,
    )

    assert "12:00" not in times(slots), "в окно 30 минут часовая услуга не влезает"


def test_lead_time_cuts_off_slots_that_are_too_soon() -> None:
    """Записаться можно минимум за час: в 12:40 слоты 13:00 и раньше уже недоступны."""
    slots = free_slots(
        work_intervals=[interval((10, 0), (18, 0))],
        busy=[],
        duration=timedelta(minutes=30),
        step=STEP,
        not_before=at(12, 40),
    )

    assert times(slots)[0] == "12:45"
    assert "12:30" not in times(slots)


def test_lead_time_after_end_of_day_gives_nothing() -> None:
    slots = free_slots(
        work_intervals=[interval((10, 0), (18, 0))],
        busy=[],
        duration=timedelta(minutes=30),
        step=STEP,
        not_before=at(23, 0),
    )

    assert slots == []


def test_busy_block_is_skipped_in_one_jump() -> None:
    """После занятого блока сетка продолжается от начала смены, а не от конца записи."""
    slots = free_slots(
        work_intervals=[interval((10, 0), (14, 0))],
        busy=[interval((10, 20), (11, 10))],
        duration=timedelta(minutes=30),
        step=STEP,
        not_before=EARLY,
    )

    assert times(slots)[:3] == ["11:15", "11:30", "11:45"]
    assert "10:00" not in times(slots), "слот 10:00-10:30 пересекается с записью в 10:20"


def test_slots_are_sorted_across_several_work_intervals() -> None:
    slots = free_slots(
        work_intervals=[interval((15, 0), (16, 0)), interval((10, 0), (11, 0))],
        busy=[],
        duration=timedelta(minutes=30),
        step=timedelta(minutes=30),
        not_before=EARLY,
    )

    assert times(slots) == ["10:00", "10:30", "15:00", "15:30"]


def test_no_working_hours_means_day_off() -> None:
    assert (
        free_slots(
            work_intervals=[],
            busy=[],
            duration=timedelta(minutes=30),
            step=STEP,
            not_before=EARLY,
        )
        == []
    )


@pytest.mark.parametrize("bad", [timedelta(0), timedelta(minutes=-15)])
def test_invalid_duration_and_step_are_rejected(bad: timedelta) -> None:
    with pytest.raises(ValueError):
        free_slots(
            work_intervals=[interval((10, 0), (18, 0))],
            busy=[],
            duration=bad,
            step=STEP,
            not_before=EARLY,
        )
    with pytest.raises(ValueError):
        free_slots(
            work_intervals=[interval((10, 0), (18, 0))],
            busy=[],
            duration=timedelta(minutes=30),
            step=bad,
            not_before=EARLY,
        )
