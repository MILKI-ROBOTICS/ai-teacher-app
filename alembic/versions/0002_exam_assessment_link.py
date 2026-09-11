"""link exams to assessments

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("exams") as batch_op:
        batch_op.add_column(sa.Column("assessment_id", sa.Integer(), sa.ForeignKey("assessments.id", name="fk_exams_assessment_id"), nullable=True))

def downgrade():
    with op.batch_alter_table("exams") as batch_op:
        batch_op.drop_column("assessment_id")


