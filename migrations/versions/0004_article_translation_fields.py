"""add translated_content columns"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0004_article_translation_fields"
down_revision = "0003_scheduler_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("articles")]
    if "translated_content" not in columns:
        op.add_column("articles", sa.Column("translated_content", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [col["name"] for col in inspector.get_columns("articles")]
    if "translated_content" in columns:
        op.drop_column("articles", "translated_content")
