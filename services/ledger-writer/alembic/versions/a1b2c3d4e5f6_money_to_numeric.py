"""Convert monetary columns from Float to Numeric (exact money)

Storing prices/quantities as double precision float allows rounding drift.
Money must be exact, so orders and trades monetary columns become NUMERIC.
Balances are already NUMERIC.

Revision ID: a1b2c3d4e5f6
Revises: f226a5a57a19
Create Date: 2026-07-27 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f226a5a57a19"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: Float -> Numeric for monetary columns."""
    # orders
    op.alter_column(
        "orders",
        "quantity",
        type_=sa.Numeric(),
        existing_nullable=False,
        postgresql_using="quantity::numeric",
    )
    op.alter_column(
        "orders",
        "filled_quantity",
        type_=sa.Numeric(),
        existing_nullable=False,
        postgresql_using="filled_quantity::numeric",
    )
    op.alter_column(
        "orders",
        "price",
        type_=sa.Numeric(),
        existing_nullable=True,
        postgresql_using="price::numeric",
    )
    op.alter_column(
        "orders",
        "average_fill_price",
        type_=sa.Numeric(),
        existing_nullable=True,
        postgresql_using="average_fill_price::numeric",
    )

    # trades (timestamp stays Float — it is a unix time, not money)
    op.alter_column(
        "trades",
        "price",
        type_=sa.Numeric(),
        existing_nullable=False,
        postgresql_using="price::numeric",
    )
    op.alter_column(
        "trades",
        "quantity",
        type_=sa.Numeric(),
        existing_nullable=False,
        postgresql_using="quantity::numeric",
    )


def downgrade() -> None:
    """Downgrade schema: Numeric -> Float for monetary columns."""
    op.alter_column(
        "trades",
        "quantity",
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using="quantity::double precision",
    )
    op.alter_column(
        "trades",
        "price",
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using="price::double precision",
    )
    op.alter_column(
        "orders",
        "average_fill_price",
        type_=sa.Float(),
        existing_nullable=True,
        postgresql_using="average_fill_price::double precision",
    )
    op.alter_column(
        "orders",
        "price",
        type_=sa.Float(),
        existing_nullable=True,
        postgresql_using="price::double precision",
    )
    op.alter_column(
        "orders",
        "filled_quantity",
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using="filled_quantity::double precision",
    )
    op.alter_column(
        "orders",
        "quantity",
        type_=sa.Float(),
        existing_nullable=False,
        postgresql_using="quantity::double precision",
    )
