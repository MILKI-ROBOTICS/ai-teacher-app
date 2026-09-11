"""offline sync and assessment grading mode

Revision ID: 0007_offline_sync_and_grading_mode
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = "0007_offline_sync_and_grading_mode"
down_revision = "0006"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("assessments") as batch:
        batch.add_column(sa.Column("grading_mode", sa.String(length=12), nullable=False, server_default="manual"))
    op.create_table(
        "sync_operations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("operation_id", sa.String(length=80), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("route", sa.String(length=120), nullable=False),
        sa.Column("method", sa.String(length=12), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_sync_operations_operation_id", "sync_operations", ["operation_id"], unique=True)
    op.create_index("ix_sync_operations_user_id", "sync_operations", ["user_id"], unique=False)

def downgrade():
    op.drop_index("ix_sync_operations_user_id", table_name="sync_operations")
    op.drop_index("ix_sync_operations_operation_id", table_name="sync_operations")
    op.drop_table("sync_operations")
    with op.batch_alter_table("assessments") as batch:
        batch.drop_column("grading_mode")
