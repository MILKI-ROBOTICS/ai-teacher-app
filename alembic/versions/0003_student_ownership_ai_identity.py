"""submission identity fields and assessment class ownership

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("classes") as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(length=20), nullable=False, server_default="active"))
    with op.batch_alter_table("subjects") as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(length=20), nullable=False, server_default="active"))
    with op.batch_alter_table("assessments") as batch_op:
        batch_op.add_column(sa.Column("class_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("status", sa.String(length=20), nullable=False, server_default="active"))
        batch_op.create_foreign_key("fk_assessments_class_id", "classes", ["class_id"], ["id"])
    with op.batch_alter_table("students") as batch_op:
        pass
    with op.batch_alter_table("questions") as batch_op:
        batch_op.create_unique_constraint("uq_exam_question_no", ["exam_id", "question_no"])
    with op.batch_alter_table("submissions") as batch_op:
        batch_op.alter_column("student_id", existing_type=sa.Integer(), nullable=True)
        batch_op.add_column(sa.Column("detected_name", sa.String(length=160), nullable=True))
        batch_op.add_column(sa.Column("detected_code", sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column("identity_confidence", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("identity_status", sa.String(length=30), nullable=False, server_default="unresolved"))


def downgrade():
    with op.batch_alter_table("submissions") as batch_op:
        batch_op.drop_column("identity_status")
        batch_op.drop_column("identity_confidence")
        batch_op.drop_column("detected_code")
        batch_op.drop_column("detected_name")
        batch_op.alter_column("student_id", existing_type=sa.Integer(), nullable=False)
    with op.batch_alter_table("questions") as batch_op:
        batch_op.drop_constraint("uq_exam_question_no", type_="unique")
    with op.batch_alter_table("assessments") as batch_op:
        batch_op.drop_constraint("fk_assessments_class_id", type_="foreignkey")
        batch_op.drop_column("status")
        batch_op.drop_column("class_id")
    with op.batch_alter_table("subjects") as batch_op:
        batch_op.drop_column("status")
    with op.batch_alter_table("classes") as batch_op:
        batch_op.drop_column("status")
