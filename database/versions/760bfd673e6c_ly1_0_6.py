"""ly1.0.6

Revision ID: 760bfd673e6c
Revises: 3762bc8215d8
Create Date: 2023-12-20 13:30:55.617947

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '760bfd673e6c'
down_revision = '3762bc8215d8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('downloadhistory', sa.Column('javdbid', sa.String(length=10), nullable=True))
    op.create_index(op.f('ix_downloadhistory_javdbid'), 'downloadhistory', ['javdbid'], unique=False)
    op.add_column('subscribe', sa.Column('javdbid', sa.String(length=10), nullable=True))
    op.create_index(op.f('ix_subscribe_javdbid'), 'subscribe', ['javdbid'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_subscribe_javdbid'), table_name='subscribe')
    op.drop_column('subscribe', 'javdbid')
    op.drop_index(op.f('ix_downloadhistory_javdbid'), table_name='downloadhistory')
    op.drop_column('downloadhistory', 'javdbid')
    # ### end Alembic commands ###