"""replace google oauth with password login

Revision ID: 002
Revises: 001
Create Date: 2026-09-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, Sequence[str], None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.execute("UPDATE users SET password_hash = '!' WHERE password_hash IS NULL")
    op.alter_column("users", "password_hash", existing_type=sa.String(length=255), nullable=False)
    op.drop_constraint("users_google_sub_key", "users", type_="unique")
    op.drop_column("users", "google_sub")
    op.drop_index("ix_users_email", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.create_index("ix_users_email", "users", ["email"], unique=False)
    op.add_column("users", sa.Column("google_sub", sa.String(length=255), nullable=True))
    op.execute("UPDATE users SET google_sub = id::text WHERE google_sub IS NULL")
    op.alter_column("users", "google_sub", existing_type=sa.String(length=255), nullable=False)
    op.create_unique_constraint("users_google_sub_key", "users", ["google_sub"])
    op.drop_column("users", "password_hash")
