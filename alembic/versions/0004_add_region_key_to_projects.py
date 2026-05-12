"""add_region_key_to_projects

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-12 13:38:34.626861

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, Sequence[str], None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add region_key column to projects table (SQLite batch mode)."""
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(
            sa.Column(
                "region_key",
                sa.String(length=64),
                nullable=False,
                server_default="iberia_868",
            ),
        )
    # Defensive backfill (server_default handles new rows; this is a no-op
    # on a fresh DB but covers any pre-existing NULL from older migrations):
    op.execute("UPDATE projects SET region_key='iberia_868' WHERE region_key IS NULL")


def downgrade() -> None:
    """Remove region_key column from projects table."""
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_column("region_key")
