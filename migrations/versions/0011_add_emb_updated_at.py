"""add updated_at to article_embeddings"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0011_add_emb_updated_at"
down_revision = "0010_add_pgvector_support"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "article_embeddings",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_column("article_embeddings", "updated_at")
