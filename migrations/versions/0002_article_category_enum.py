"""enforce article category enum"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0002_article_category_enum"
down_revision = "0001_init_schema"
branch_labels = None
depends_on = None

article_category_enum = sa.Enum(
    "frontier",
    "fda_policy",
    "ema_policy",
    "pmda_policy",
    "project_apply",
    name="article_category",
)


def upgrade() -> None:
    bind = op.get_bind()
    article_category_enum.create(bind, checkfirst=True)

    # 清理旧数据，避免历史分类污染
    op.execute("DELETE FROM ai_results")
    op.execute("DELETE FROM articles")
    op.execute("DELETE FROM sources")

    op.alter_column(
        "sources",
        "category",
        existing_type=sa.String(length=64),
        type_=article_category_enum,
        existing_nullable=True,
        nullable=False,
        postgresql_using="category::article_category",
    )
    op.alter_column(
        "articles",
        "category",
        existing_type=sa.String(length=64),
        type_=article_category_enum,
        nullable=False,
        postgresql_using="category::article_category",
    )


def downgrade() -> None:
    op.alter_column(
        "articles",
        "category",
        existing_type=article_category_enum,
        type_=sa.String(length=64),
        nullable=False,
    )
    op.alter_column(
        "sources",
        "category",
        existing_type=article_category_enum,
        type_=sa.String(length=64),
        nullable=True,
    )
    article_category_enum.drop(op.get_bind(), checkfirst=True)
