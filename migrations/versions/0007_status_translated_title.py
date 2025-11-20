"""add translated_title/status and drop apply_status/sub_category legacy"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0007_status_translated_title"
down_revision = "0006_conversation_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {col["name"] for col in inspector.get_columns("articles")}

    if "translated_title" not in cols:
        op.add_column("articles", sa.Column("translated_title", sa.String(length=512), nullable=True))
    if "status" not in cols:
        op.add_column("articles", sa.Column("status", sa.String(length=64), nullable=True))
    if "apply_status" in cols:
        op.drop_column("articles", "apply_status")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cols = {col["name"] for col in inspector.get_columns("articles")}

    if "status" in cols:
        op.drop_column("articles", "status")
    if "translated_title" in cols:
        op.drop_column("articles", "translated_title")
    if "apply_status" not in cols:
        op.add_column("articles", sa.Column("apply_status", sa.String(length=16), nullable=True))
