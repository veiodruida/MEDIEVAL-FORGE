"""make_v1_legacy_fields_nullable_for_v3

Make country_qid, period_start, period_end nullable so the v3 POST /projects
endpoint can create projects with only {name, region_key} — v1 fields are
optional for v3 projects and are not used by the geometry pipeline.

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-12 13:41:24.242798

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Make v1 legacy fields nullable (SQLite batch mode)."""
    with op.batch_alter_table("projects") as batch_op:
        batch_op.alter_column(
            "country_qid",
            existing_type=sa.String(length=200),
            nullable=True,
        )
        batch_op.alter_column(
            "period_start",
            existing_type=sa.Integer(),
            nullable=True,
        )
        batch_op.alter_column(
            "period_end",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    """Restore v1 legacy fields to NOT NULL (SQLite batch mode)."""
    with op.batch_alter_table("projects") as batch_op:
        batch_op.alter_column(
            "period_end",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.alter_column(
            "period_start",
            existing_type=sa.Integer(),
            nullable=False,
        )
        batch_op.alter_column(
            "country_qid",
            existing_type=sa.String(length=200),
            nullable=False,
        )
