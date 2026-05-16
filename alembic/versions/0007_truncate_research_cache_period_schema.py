"""Truncate research_cache for period schema change.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-16

D-04: forward-only. cache_key derivation changes incompatibly — period_label string
component swaps to f"{period_start}|{period_end}". Re-key heuristic rejected
(single-user local app; re-running research is cheap). Downgrade is a no-op.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM research_cache")


def downgrade() -> None:
    # No-op — D-04 mandates forward-only.
    pass
