"""ly1.0.4

Revision ID: 80ce004d2401
Revises: b4a0865028f5
Create Date: 2023-12-14 05:10:28.395644

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '80ce004d2401'
down_revision = 'b4a0865028f5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('subscribe', sa.Column('save_path', sa.String(length=255), nullable=True))
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('subscribe', 'save_path')
    # ### end Alembic commands ###
