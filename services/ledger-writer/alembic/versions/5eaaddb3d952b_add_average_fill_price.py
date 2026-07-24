"""add average_fill_price

Revision ID: 5eaaddb3d952b
Revises: 4daddb3d952a
Create Date: 2026-07-24 10:28:19.053464

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5eaaddb3d952b"
down_revision: Union[str, Sequence[str], None] = "4daddb3d952a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("orders", sa.Column("average_fill_price", sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("orders", "average_fill_price")
