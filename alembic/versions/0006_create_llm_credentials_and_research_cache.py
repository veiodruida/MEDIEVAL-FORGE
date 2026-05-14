"""create llm_credentials and research_cache tables

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-14

Phase 07 (D-06 + D-11): DB-backed credential store + research cache.
REVIEWS fix #2 (2026-05-14): research_cache uses `generated_at` (not `created_at`)
to disambiguate from research_overlay.meta.json::applied_at (Plan 07b).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "llm_credentials",
        sa.Column("provider_id", sa.String(length=50), primary_key=True),
        sa.Column("credential_type", sa.String(length=50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "research_cache",
        sa.Column("cache_key", sa.String(length=64), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("generated_at", sa.DateTime(), nullable=False),  # REVIEWS fix #2
    )


def downgrade() -> None:
    op.drop_table("research_cache")
    op.drop_table("llm_credentials")
