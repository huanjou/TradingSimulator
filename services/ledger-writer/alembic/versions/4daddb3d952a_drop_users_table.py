"""drop users table

Revision ID: 4daddb3d952a
Revises: c40dd19f99dc
Create Date: 2026-07-23 20:43:19.053464

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4daddb3d952a"
down_revision: Union[str, Sequence[str], None] = "c40dd19f99dc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint("orders_user_id_fkey", "orders", type_="foreignkey")
    op.drop_index(op.f("ix_users_id"), table_name="users", if_exists=True)
    op.drop_index(op.f("ix_users_email"), table_name="users", if_exists=True)
    op.drop_table("users")


def downgrade() -> None:
    """Downgrade schema."""
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), autoincrement=False, nullable=False),
        sa.Column("email", sa.VARCHAR(length=255), autoincrement=False, nullable=False),
        sa.Column(
            "hashed_password",
            sa.VARCHAR(length=255),
            autoincrement=False,
            nullable=False,
        ),
        sa.Column("is_active", sa.BOOLEAN(), autoincrement=False, nullable=True),
        sa.Column("is_superuser", sa.BOOLEAN(), autoincrement=False, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            autoincrement=False,
            nullable=True,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), autoincrement=False, nullable=True
        ),
        sa.PrimaryKeyConstraint("id", name="users_pkey"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_id", "users", ["id"], unique=False)
    op.create_foreign_key("orders_user_id_fkey", "orders", "users", ["user_id"], ["id"])
