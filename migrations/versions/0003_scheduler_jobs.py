"""scheduler job tables"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0003_scheduler_jobs"
down_revision = "0002_article_category_enum"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "crawler_jobs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("crawler_name", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.String(length=36), sa.ForeignKey("sources.id")),
        sa.Column("job_type", sa.String(length=16), nullable=False),
        sa.Column("schedule_cron", sa.String(length=128)),
        sa.Column("interval_minutes", sa.Integer()),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_status", sa.String(length=16)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("timezone('utc', now())")),
    )

    op.create_table(
        "crawler_job_runs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("job_id", sa.String(length=64), sa.ForeignKey("crawler_jobs.id", ondelete="CASCADE")),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("executed_crawler", sa.String(length=128), nullable=False),
        sa.Column("params_snapshot", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("log_path", sa.String(length=255)),
        sa.Column("error_message", sa.Text()),
    )


def downgrade() -> None:
    op.drop_table("crawler_job_runs")
    op.drop_table("crawler_jobs")
