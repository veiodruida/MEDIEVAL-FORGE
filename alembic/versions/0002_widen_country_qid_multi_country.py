"""widen projects.country_qid to support comma-separated multi-country lists"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.alter_column(
            "country_qid",
            existing_type=sa.String(length=20),
            type_=sa.String(length=200),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch:
        batch.alter_column(
            "country_qid",
            existing_type=sa.String(length=200),
            type_=sa.String(length=20),
            existing_nullable=False,
        )
