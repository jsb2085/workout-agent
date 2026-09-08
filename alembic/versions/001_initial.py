"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-09-05

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("google_sub", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("google_sub"),
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "lifting_workouts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("lift", sa.String(length=255), nullable=False),
        sa.Column("goal_weight", sa.String(length=64), nullable=False),
        sa.Column("reps", sa.Integer(), nullable=False),
        sa.Column("actual_weight", sa.String(length=64), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("date_todo", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lifting_workouts_user_id", "lifting_workouts", ["user_id"])
    op.create_index("ix_lifting_workouts_date_todo", "lifting_workouts", ["date_todo"])

    op.create_table(
        "cardio",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("sprint", sa.Boolean(), nullable=False),
        sa.Column("run", sa.Boolean(), nullable=False),
        sa.Column("walk", sa.Boolean(), nullable=False),
        sa.Column("distance", sa.String(length=64), nullable=False),
        sa.Column("reps", sa.Integer(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False),
        sa.Column("date_todo", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cardio_user_id", "cardio", ["user_id"])
    op.create_index("ix_cardio_date_todo", "cardio", ["date_todo"])

    op.create_table(
        "gym_location",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("location_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gym_location_user_id", "gym_location", ["user_id"])

    op.create_table(
        "performance_goals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("goal_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_performance_goals_user_id", "performance_goals", ["user_id"])

    op.create_table(
        "physic_photos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("is_goal", sa.Boolean(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_physic_photos_user_id", "physic_photos", ["user_id"])
    op.create_index("ix_physic_photos_date", "physic_photos", ["date"])

    op.create_table(
        "protein",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("grams_goal", sa.Integer(), nullable=False),
        sa.Column("grams_actual", sa.Integer(), nullable=False),
        sa.Column("date_todo", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_protein_user_id", "protein", ["user_id"])
    op.create_index("ix_protein_date_todo", "protein", ["date_todo"])

    op.create_table(
        "steps",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("steps_goal", sa.Integer(), nullable=False),
        sa.Column("steps_actual", sa.Integer(), nullable=False),
        sa.Column("date_todo", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_steps_user_id", "steps", ["user_id"])
    op.create_index("ix_steps_date_todo", "steps", ["date_todo"])


def downgrade() -> None:
    op.drop_table("steps")
    op.drop_table("protein")
    op.drop_table("physic_photos")
    op.drop_table("performance_goals")
    op.drop_table("gym_location")
    op.drop_table("cardio")
    op.drop_table("lifting_workouts")
    op.drop_table("users")
