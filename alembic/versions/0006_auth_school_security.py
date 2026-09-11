"""add workspace ownership and session versioning

Revision ID: 0006
down_revision: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("school_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="1"))
    op.create_index("ix_users_school_id", "users", ["school_id"])
    conn = op.get_bind()
    school = conn.execute(sa.text("SELECT id FROM schools ORDER BY id LIMIT 1")).first()
    if school:
        conn.execute(sa.text("UPDATE users SET school_id = :sid WHERE school_id IS NULL"), {"sid": school[0]})
    # No synthetic school is created during migration. Production workspaces are created only during explicit sign-up.


def downgrade():
    op.drop_index("ix_users_school_id", table_name="users")
    op.drop_column("users", "session_version")
    op.drop_column("users", "school_id")
