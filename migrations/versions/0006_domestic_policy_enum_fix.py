"""recreate enum to ensure domestic policy value exists"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0006_domestic_policy_enum_fix"
down_revision = "0005_domestic_policy_enum"
branch_labels = None
depends_on = None

OLD_TYPE = sa.Enum(
    "frontier",
    "fda_policy",
    "ema_policy",
    "pmda_policy",
    "project_apply",
    name="article_category",
)

NEW_VALUES = (
    "frontier",
    "fda_policy",
    "ema_policy",
    "pmda_policy",
    "project_apply",
    "domestic_policy",
)

NEW_TYPE = sa.Enum(*NEW_VALUES, name="article_category_new")


def upgrade() -> None:
    bind = op.get_bind()
    NEW_TYPE.create(bind, checkfirst=True)

    op.execute(
        "ALTER TABLE sources ALTER COLUMN category TYPE article_category_new "
        "USING category::text::article_category_new"
    )
    op.execute(
        "ALTER TABLE articles ALTER COLUMN category TYPE article_category_new "
        "USING category::text::article_category_new"
    )

    op.execute("DROP TYPE article_category")
    op.execute("ALTER TYPE article_category_new RENAME TO article_category")


def downgrade() -> None:
    op.execute("ALTER TYPE article_category RENAME TO article_category_with_domestic")
    OLD_TYPE.create(op.get_bind(), checkfirst=True)
    op.execute(
        "DELETE FROM articles WHERE category = 'domestic_policy'"
    )
    op.execute(
        "DELETE FROM sources WHERE category = 'domestic_policy'"
    )
    op.execute(
        "ALTER TABLE sources ALTER COLUMN category TYPE article_category "
        "USING category::text::article_category"
    )
    op.execute(
        "ALTER TABLE articles ALTER COLUMN category TYPE article_category "
        "USING category::text::article_category"
    )
    op.execute("DROP TYPE article_category_with_domestic")
