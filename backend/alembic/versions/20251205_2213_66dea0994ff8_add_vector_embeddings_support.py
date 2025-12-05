"""add_vector_embeddings_support

Revision ID: 66dea0994ff8
Revises: 0d4f47db8f8b
Create Date: 2025-12-05 22:13:19.664205+00:00

"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision = '66dea0994ff8'
down_revision = '0d4f47db8f8b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add profile embedding vector column to users table
    # Using 1536 dimensions for OpenAI text-embedding-ada-002 compatibility
    op.add_column('users', sa.Column('profile_embedding', Vector(1536), nullable=True))

    # Create index for vector similarity search on users
    op.execute('CREATE INDEX users_profile_embedding_idx ON users USING ivfflat (profile_embedding vector_cosine_ops) WITH (lists = 100)')

    # Add embedding column to user_memory table for storing aggregated user learning patterns
    op.add_column('user_memory', sa.Column('learning_pattern_embedding', Vector(1536), nullable=True))

    # Create index for vector similarity search on user_memory
    op.execute('CREATE INDEX user_memory_learning_pattern_embedding_idx ON user_memory USING ivfflat (learning_pattern_embedding vector_cosine_ops) WITH (lists = 100)')

    # Create interaction_logs table for tracking all user interactions
    op.create_table(
        'interaction_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('interaction_type', sa.String(50), nullable=False),  # 'exercise_completion', 'chat_message', 'hint_request', etc.
        sa.Column('context_type', sa.String(50), nullable=True),  # 'exercise', 'chat', 'code_review', etc.
        sa.Column('context_id', sa.Integer(), nullable=True),  # ID of related entity (exercise_id, conversation_id, etc.)
        sa.Column('interaction_data', sa.JSON(), nullable=True),  # Flexible storage for interaction details
        sa.Column('interaction_embedding', Vector(1536), nullable=True),  # Embedding of interaction for similarity search
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for interaction_logs
    op.create_index('interaction_logs_user_id_idx', 'interaction_logs', ['user_id'])
    op.create_index('interaction_logs_created_at_idx', 'interaction_logs', ['created_at'])
    op.create_index('interaction_logs_interaction_type_idx', 'interaction_logs', ['interaction_type'])
    op.execute('CREATE INDEX interaction_logs_embedding_idx ON interaction_logs USING ivfflat (interaction_embedding vector_cosine_ops) WITH (lists = 100)')


def downgrade() -> None:
    # Drop interaction_logs table and its indexes
    op.drop_index('interaction_logs_embedding_idx', table_name='interaction_logs')
    op.drop_index('interaction_logs_interaction_type_idx', table_name='interaction_logs')
    op.drop_index('interaction_logs_created_at_idx', table_name='interaction_logs')
    op.drop_index('interaction_logs_user_id_idx', table_name='interaction_logs')
    op.drop_table('interaction_logs')

    # Drop user_memory indexes and columns
    op.drop_index('user_memory_learning_pattern_embedding_idx', table_name='user_memory')
    op.drop_column('user_memory', 'learning_pattern_embedding')

    # Drop users indexes and columns
    op.drop_index('users_profile_embedding_idx', table_name='users')
    op.drop_column('users', 'profile_embedding')
