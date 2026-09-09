"""create audits table

Revision ID: 001_create_audits_table
Revises: 
Create Date: 2026-09-01 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001_create_audits_table'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table(
        'audits',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('caption', sa.Text(), nullable=False),
        sa.Column('promoted_site', sa.Text(), nullable=True),
        sa.Column('override_url', sa.Text(), nullable=True),
        sa.Column('claims', sa.JSON(), nullable=True),
        sa.Column('crawl_status', sa.String(length=50), nullable=True),
        sa.Column('verdicts', sa.JSON(), nullable=True),
        sa.Column('confidence_tier', sa.String(length=50), nullable=True),
        sa.Column('coverage_status', sa.String(length=50), nullable=True),
        sa.Column('summary_label', sa.Text(), nullable=True),
        sa.Column('facts', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade() -> None:
    op.drop_table('audits')
