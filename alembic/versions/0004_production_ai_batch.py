"""production AI batch jobs and school pass mark

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("schools") as batch_op:
        batch_op.add_column(sa.Column("pass_mark", sa.Float(), nullable=False, server_default="50"))
    op.create_table(
        "scan_batch_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exams.id"), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("total_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("succeeded_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    with op.batch_alter_table("submissions") as batch_op:
        batch_op.add_column(sa.Column("batch_job_id", sa.Integer(), sa.ForeignKey("scan_batch_jobs.id", name="fk_submissions_batch_job_id"), nullable=True))


def downgrade():
    with op.batch_alter_table("submissions") as batch_op:
        batch_op.drop_column("batch_job_id")
    op.drop_table("scan_batch_jobs")
    with op.batch_alter_table("schools") as batch_op:
        batch_op.drop_column("pass_mark")
