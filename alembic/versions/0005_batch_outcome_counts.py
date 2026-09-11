"""track batch auto-store and review-required outcomes"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("scan_batch_jobs") as batch_op:
        batch_op.add_column(sa.Column("auto_stored_files", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("review_required_files", sa.Integer(), nullable=False, server_default="0"))

def downgrade():
    with op.batch_alter_table("scan_batch_jobs") as batch_op:
        batch_op.drop_column("review_required_files")
        batch_op.drop_column("auto_stored_files")
