"""Add indexes to user model for performance

Revision ID: add_indexes_perf
Revises: 0d4f47db8f8b
Create Date: 2025-12-05

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_indexes_perf'
down_revision = '0d4f47db8f8b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add indexes to frequently queried columns
    op.create_index(
        'ix_users_github_id',
        'users',
        ['github_id'],
        unique=False,
        postgresql_where=sa.text('github_id IS NOT NULL')
    )

    op.create_index(
        'ix_users_google_id',
        'users',
        ['google_id'],
        unique=False,
        postgresql_where=sa.text('google_id IS NOT NULL')
    )

    op.create_index(
        'ix_users_last_exercise_date',
        'users',
        ['last_exercise_date'],
        unique=False,
        postgresql_where=sa.text('last_exercise_date IS NOT NULL')
    )

    op.create_index(
        'ix_users_created_at',
        'users',
        ['created_at'],
        unique=False
    )


def downgrade() -> None:
    # Remove indexes in reverse order
    op.drop_index('ix_users_created_at', table_name='users')
    op.drop_index('ix_users_last_exercise_date', table_name='users')
    op.drop_index('ix_users_google_id', table_name='users')
    op.drop_index('ix_users_github_id', table_name='users')
