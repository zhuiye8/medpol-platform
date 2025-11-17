"""add domestic policy value to article_category enum"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "0005_domestic_policy_enum"
down_revision = "0004_article_translation_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE article_category ADD VALUE IF NOT EXISTS 'domestic_policy'")


def downgrade() -> None:
    # PostgreSQL 无法直接删除 enum 取值，这里保留空实现
    pass
