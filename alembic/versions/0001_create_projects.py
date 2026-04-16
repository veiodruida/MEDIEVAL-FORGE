"""create projects table

Revision ID: 0001
Revises:
Create Date: 2026-04-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("country_qid", sa.String(length=20), nullable=False),
        sa.Column("period_start", sa.Integer(), nullable=False),
        sa.Column("period_end", sa.Integer(), nullable=False),
        sa.Column("bbox_lon_min", sa.Float(), nullable=True),
        sa.Column("bbox_lon_max", sa.Float(), nullable=True),
        sa.Column("bbox_lat_min", sa.Float(), nullable=True),
        sa.Column("bbox_lat_max", sa.Float(), nullable=True),
        sa.Column("generator_config", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False, server_default="created"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("projects")
