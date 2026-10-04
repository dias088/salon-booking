"""views for schedule and catalog

Два представления. Они не «украшение»: на v_appointment_details держатся
админ-календарь и расписание мастера (одним запросом вместо пяти JOIN в ORM),
а v_master_service_offer прячет COALESCE-логику «цена мастера или общая цена»,
чтобы она не дублировалась в каждом месте кода.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-04
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


V_MASTER_SERVICE_OFFER = """
CREATE VIEW v_master_service_offer AS
SELECT
    m.id                                               AS master_id,
    mu.full_name                                       AS master_name,
    m.photo_url                                        AS master_photo_url,
    m.is_active                                        AS master_is_active,
    s.id                                               AS service_id,
    s.name                                             AS service_name,
    s.is_active                                        AS service_is_active,
    sc.id                                              AS category_id,
    sc.name                                            AS category_name,
    sc.sort_order                                      AS category_sort_order,
    -- Собственные цена и длительность мастера перебивают общие.
    COALESCE(ms.price_override, s.price)               AS price,
    COALESCE(ms.duration_min_override, s.duration_min) AS duration_min,
    (ms.price_override IS NOT NULL)                    AS has_custom_price,
    (ms.duration_min_override IS NOT NULL)             AS has_custom_duration
FROM master_services ms
JOIN masters            m  ON m.id  = ms.master_id
JOIN users              mu ON mu.id = m.user_id
JOIN services           s  ON s.id  = ms.service_id
JOIN service_categories sc ON sc.id = s.category_id
"""

V_APPOINTMENT_DETAILS = """
CREATE VIEW v_appointment_details AS
SELECT
    a.id,
    a.status,
    lower(a.period) AS starts_at,
    upper(a.period) AS ends_at,
    (EXTRACT(EPOCH FROM (upper(a.period) - lower(a.period))) / 60)::int AS duration_min,
    a.price_at_booking,
    a.comment,
    a.created_at,
    a.cancelled_at,
    a.client_id,
    cu.full_name AS client_name,
    cu.phone     AS client_phone,
    cu.email     AS client_email,
    a.master_id,
    mu.full_name AS master_name,
    a.service_id,
    s.name       AS service_name,
    sc.id        AS category_id,
    sc.name      AS category_name
FROM appointments a
JOIN users              cu ON cu.id = a.client_id
JOIN masters            m  ON m.id  = a.master_id
JOIN users              mu ON mu.id = m.user_id
JOIN services           s  ON s.id  = a.service_id
JOIN service_categories sc ON sc.id = s.category_id
"""


def upgrade() -> None:
    op.execute(V_MASTER_SERVICE_OFFER)
    op.execute(V_APPOINTMENT_DETAILS)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS v_appointment_details")
    op.execute("DROP VIEW IF EXISTS v_master_service_offer")
