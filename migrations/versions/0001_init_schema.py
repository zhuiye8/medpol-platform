"""init schema"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001_init_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("label", sa.String(length=64), nullable=True),
        sa.Column("base_url", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("meta", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "articles",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("content_html", sa.Text(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False),
        sa.Column("publish_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_name", sa.String(length=128), nullable=False),
        sa.Column("source_url", sa.String(length=512), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("crawl_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_source", sa.String(length=32), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("ai_analysis", sa.JSON(), nullable=True),
        sa.Column("translated_content", sa.Text(), nullable=True),
        sa.Column("translated_content_html", sa.Text(), nullable=True),
        sa.Column("original_source_language", sa.String(length=16), nullable=True),
        sa.Column("apply_status", sa.String(length=16), nullable=True, server_default="pending"),
        sa.Column("is_positive_policy", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "ai_results",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("article_id", sa.String(length=64), nullable=False),
        sa.Column("task_type", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("output", sa.Text(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["article_id"], ["articles.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("ai_results")
    op.drop_table("articles")
    op.drop_table("sources")
