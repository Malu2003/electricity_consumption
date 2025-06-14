"""Fixed User model authentication

Revision ID: b47c718d5846
Revises: 607fccb0d2a5
Create Date: 2025-03-11 01:47:22.682212

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import String


# revision identifiers, used by Alembic.
revision: str = 'b47c718d5846'
down_revision: Union[str, None] = '607fccb0d2a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Step 1: Add 'hashed_password' as NULLABLE first
    op.add_column('users', sa.Column('hashed_password', sa.String(), nullable=True))

    # Step 2: Set a default value for existing rows (temporary fix)
    users_table = table("users", column("hashed_password", String))
    op.execute(users_table.update().values(hashed_password="default_hash"))  # Change as needed

    # Step 3: Make 'hashed_password' NOT NULL
    op.alter_column("users", "hashed_password", nullable=False)

    # Step 4: Drop the old 'password' column
    op.drop_column('users', 'password')


def downgrade() -> None:
    """Downgrade schema."""
    # Step 1: Re-add 'password' column as NULLABLE
    op.add_column('users', sa.Column('password', sa.VARCHAR(), autoincrement=False, nullable=True))

    # Step 2: Copy hashed_password back to password (if needed)
    users_table = table("users", column("password", String), column("hashed_password", String))
    op.execute(users_table.update().values(password="password_placeholder"))  # Adjust as necessary

    # Step 3: Make 'password' NOT NULL
    op.alter_column("users", "password", nullable=False)

    # Step 4: Drop 'hashed_password'
    op.drop_column('users', 'hashed_password')
