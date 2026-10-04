"""Импорт всех моделей в одном месте.

Alembic и SQLAlchemy должны увидеть каждый класс до первого обращения
к Base.metadata, иначе строковые ссылки в relationship не разрешатся.
"""

from app.db.models.appointment import Appointment
from app.db.models.enums import (
    BLOCKING_STATUSES,
    CONSTRAINED_STATUSES,
    AppointmentStatus,
    UserRole,
)
from app.db.models.master import Master, TimeOff, WorkingHours
from app.db.models.service import MasterService, Service, ServiceCategory
from app.db.models.user import RefreshToken, User

__all__ = [
    "BLOCKING_STATUSES",
    "CONSTRAINED_STATUSES",
    "Appointment",
    "AppointmentStatus",
    "Master",
    "MasterService",
    "RefreshToken",
    "Service",
    "ServiceCategory",
    "TimeOff",
    "User",
    "UserRole",
    "WorkingHours",
]
