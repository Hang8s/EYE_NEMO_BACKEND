"""initial archive schema
Revision ID: 0001_initial
Revises:
"""
from alembic import op
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None
def upgrade() -> None:
    from app.db.base import Base
    import app.db.models  # noqa: F401
    bind = op.get_bind(); Base.metadata.create_all(bind=bind)
def downgrade() -> None:
    from app.db.base import Base
    import app.db.models  # noqa: F401
    Base.metadata.drop_all(bind=op.get_bind())
