"""add submitter_token and feedback to audits table

Revision ID: 003_add_feedback_and_submitter_token
Revises: 002_create_api_keys_table
Create Date: 2026-09-09 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003_add_feedback_and_submitter_token'
down_revision = '002_create_api_keys_table'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('audits', sa.Column('submitter_token', sa.String(length=64), nullable=True))
    op.add_column('audits', sa.Column('feedback', sa.JSON(), nullable=True))
    try:
        op.create_index(op.f('ix_audits_submitter_token'), 'audits', ['submitter_token'], unique=False)
    except Exception:
        pass

def downgrade() -> None:
    try:
        op.drop_index(op.f('ix_audits_submitter_token'), table_name='audits')
    except Exception:
        pass
    op.drop_column('audits', 'feedback')
    op.drop_column('audits', 'submitter_token')
