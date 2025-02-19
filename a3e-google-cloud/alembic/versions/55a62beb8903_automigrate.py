"""automigrate

Revision ID: 55a62beb8903
Revises: cabebe42f7fa
Create Date: 2024-07-07 21:49:57.272561

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '55a62beb8903'
down_revision: Union[str, None] = 'cabebe42f7fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('admin_options')
    op.add_column('button_request', sa.Column('folder_name', sa.String(length=255), nullable=True))
    op.add_column('button_request', sa.Column('folder_url', sa.String(length=255), nullable=True))
    op.add_column('button_request', sa.Column('upload_only_url', sa.String(length=255), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('button_request', 'upload_only_url')
    op.drop_column('button_request', 'folder_url')
    op.drop_column('button_request', 'folder_name')
    op.create_table('admin_options',
    sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
    sa.Column('stripe_options', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=False),
    sa.PrimaryKeyConstraint('id', name='admin_options_pkey'),
    sa.UniqueConstraint('id', name='admin_options_id_key')
    )
    # ### end Alembic commands ###
