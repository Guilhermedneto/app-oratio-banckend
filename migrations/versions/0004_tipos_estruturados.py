"""tipos estruturados de conteúdo (santo, novena, mistérios, horas)

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

KINDS = "'oracao','texto','reflexao','rito','terco','hora','santo','novena','misterio'"
OLD_KINDS = "'oracao','texto','reflexao','rito','terco'"


def upgrade() -> None:
    op.add_column(
        "managed_contents",
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.drop_constraint("ck_content_kind", "managed_contents", type_="check")
    op.create_check_constraint("ck_content_kind", "managed_contents", f"kind in ({KINDS})")
    op.drop_constraint("ck_rosary_set", "rosary_log", type_="check")
    op.alter_column("rosary_log", "mystery_set", type_=sa.String(60), existing_nullable=False)


def downgrade() -> None:
    op.alter_column("rosary_log", "mystery_set", type_=sa.String(12), existing_nullable=False)
    op.create_check_constraint(
        "ck_rosary_set",
        "rosary_log",
        "mystery_set in ('gozosos','dolorosos','gloriosos','luminosos')",
    )
    op.drop_constraint("ck_content_kind", "managed_contents", type_="check")
    op.create_check_constraint("ck_content_kind", "managed_contents", f"kind in ({OLD_KINDS})")
    op.drop_column("managed_contents", "data")
