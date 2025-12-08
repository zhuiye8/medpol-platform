"""add pgvector extension and article_embeddings table"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = "0010_add_pgvector_support"
down_revision = "0009_drop_conversation_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "article_embeddings",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("article_id", sa.String(length=64), sa.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("model_name", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "idx_article_embeddings_vector",
        "article_embeddings",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_with={"lists": "100"},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("idx_article_embeddings_vector", table_name="article_embeddings")
    op.drop_table("article_embeddings")
    # 保留 pgvector 扩展，防止其他对象依赖；如需彻底清理，可手动删除
