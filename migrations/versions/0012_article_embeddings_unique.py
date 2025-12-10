"""add unique constraint on article_embeddings (article_id, chunk_index)"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0012_article_embeddings_unique"
down_revision = "0011_add_emb_updated_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 先清理可能存在的重复数据，保留最新的记录
    op.execute("""
        DELETE FROM article_embeddings a
        USING article_embeddings b
        WHERE a.article_id = b.article_id
          AND a.chunk_index = b.chunk_index
          AND a.created_at < b.created_at
    """)

    # 添加唯一约束
    op.create_unique_constraint(
        "uq_article_embeddings_article_chunk",
        "article_embeddings",
        ["article_id", "chunk_index"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_article_embeddings_article_chunk",
        "article_embeddings",
        type_="unique",
    )
