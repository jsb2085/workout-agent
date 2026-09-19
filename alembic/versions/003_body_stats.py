"""add body_stats

Revision ID: 003
Revises: 002
Create Date: 2026-09-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, Sequence[str], None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "body_stats",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("height", sa.String(length=64), nullable=False),
        sa.Column("weight", sa.String(length=64), nullable=False),
        sa.Column("squat", sa.String(length=64), nullable=True),
        sa.Column("bench", sa.String(length=64), nullable=True),
        sa.Column("deadlift", sa.String(length=64), nullable=True),
        sa.Column("overhead_press", sa.String(length=64), nullable=True),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_body_stats_user_id", "body_stats", ["user_id"])
    op.create_index("ix_body_stats_date", "body_stats", ["date"])


def downgrade() -> None:
    op.drop_table("body_stats")
