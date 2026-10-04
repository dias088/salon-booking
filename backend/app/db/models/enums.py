"""Перечисления домена.

В курсовой схеме статус визита был VARCHAR(20) с CHECK IN (...).
Здесь это настоящие PostgreSQL ENUM: типобезопаснее, компактнее в индексе
и видны в \\dT.  Значения переименованы в snake_case:
'Scheduled' -> 'booked', 'No-show' -> 'no_show'.
"""

from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    client = "client"
    master = "master"
    admin = "admin"


class AppointmentStatus(str, enum.Enum):
    booked = "booked"
    completed = "completed"
    cancelled = "cancelled"
    no_show = "no_show"

    @property
    def is_final(self) -> bool:
        return self is not AppointmentStatus.booked


#: Единственный статус в WHERE частичного EXCLUDE-ограничения
#: appointments_no_overlap. Шире брать нельзя: ограничение должно пускать
#: новую запись на время, с которого бронь уже снята.
CONSTRAINED_STATUSES: frozenset[AppointmentStatus] = frozenset(
    {AppointmentStatus.booked},
)

#: Статусы, при которых время мастера считается занятым при поиске слотов.
#: Отменённая запись слот освобождает — остальные нет, включая no_show:
#: время было выделено клиенту, даже если он не пришёл.
BLOCKING_STATUSES: frozenset[AppointmentStatus] = frozenset(
    status for status in AppointmentStatus if status is not AppointmentStatus.cancelled
)
