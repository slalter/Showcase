"""automigrate

Revision ID: e055ced7f5fb
Revises: 5fcee6b02afc
Create Date: 2024-05-28 16:43:22.218161

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e055ced7f5fb'
down_revision: Union[str, None] = '5fcee6b02afc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('button_request', 'stripe_session_url',
               existing_type=sa.VARCHAR(length=255),
               type_=sa.String(length=510),
               existing_nullable=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('button_request', 'stripe_session_url',
               existing_type=sa.String(length=510),
               type_=sa.VARCHAR(length=255),
               existing_nullable=False)
    # ### end Alembic commands ###
