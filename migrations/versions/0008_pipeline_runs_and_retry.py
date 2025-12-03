"""add pipeline run tables and retry/log fields"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0008_pipeline_runs_and_retry"
down_revision = "0007_status_translated_title"
branch_labels = None
depends_on = None


def _has_column(inspector, table: str, column: str) -> bool:
    return column in {col["name"] for col in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not _has_column(inspector, "crawler_jobs", "retry_config"):
        op.add_column("crawler_jobs", sa.Column("retry_config", sa.JSON(), nullable=True, server_default=sa.text("'{}'")))

    if not _has_column(inspector, "crawler_job_runs", "duration_ms"):
        op.add_column("crawler_job_runs", sa.Column("duration_ms", sa.Integer(), nullable=True, server_default="0"))
    if not _has_column(inspector, "crawler_job_runs", "retry_attempts"):
        op.add_column("crawler_job_runs", sa.Column("retry_attempts", sa.Integer(), nullable=True, server_default="0"))
    if not _has_column(inspector, "crawler_job_runs", "error_type"):
        op.add_column("crawler_job_runs", sa.Column("error_type", sa.String(length=32), nullable=True))
    if not _has_column(inspector, "crawler_job_runs", "pipeline_run_id"):
        op.add_column("crawler_job_runs", sa.Column("pipeline_run_id", sa.String(length=64), nullable=True))

    if "crawler_pipeline_runs" not in inspector.get_table_names():
        op.create_table(
            "crawler_pipeline_runs",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("run_type", sa.String(length=16), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("total_crawlers", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("successful_crawlers", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("failed_crawlers", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_articles", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
        )

    if "crawler_pipeline_run_details" not in inspector.get_table_names():
        op.create_table(
            "crawler_pipeline_run_details",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column(
                "run_id",
                sa.String(length=64),
                sa.ForeignKey("crawler_pipeline_runs.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("crawler_name", sa.String(length=128), nullable=False),
            sa.Column("source_id", sa.String(length=36), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("duration_ms", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("attempt_number", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=True, server_default="0"),
            sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_type", sa.String(length=32), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("log_path", sa.String(length=255), nullable=True),
            sa.Column("config_snapshot", sa.JSON(), nullable=True),
        )
        op.create_index(
            "idx_pipeline_run_details_run_id",
            "crawler_pipeline_run_details",
            ["run_id"],
        )
        op.create_index(
            "idx_pipeline_run_details_status",
            "crawler_pipeline_run_details",
            ["status"],
        )
        op.create_index(
            "idx_pipeline_run_details_crawler",
            "crawler_pipeline_run_details",
            ["crawler_name"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if _has_column(inspector, "crawler_job_runs", "pipeline_run_id"):
        op.drop_column("crawler_job_runs", "pipeline_run_id")
    if _has_column(inspector, "crawler_job_runs", "error_type"):
        op.drop_column("crawler_job_runs", "error_type")
    if _has_column(inspector, "crawler_job_runs", "retry_attempts"):
        op.drop_column("crawler_job_runs", "retry_attempts")
    if _has_column(inspector, "crawler_job_runs", "duration_ms"):
        op.drop_column("crawler_job_runs", "duration_ms")

    if _has_column(inspector, "crawler_jobs", "retry_config"):
        op.drop_column("crawler_jobs", "retry_config")

    if "crawler_pipeline_run_details" in inspector.get_table_names():
        op.drop_index("idx_pipeline_run_details_crawler", table_name="crawler_pipeline_run_details")
        op.drop_index("idx_pipeline_run_details_status", table_name="crawler_pipeline_run_details")
        op.drop_index("idx_pipeline_run_details_run_id", table_name="crawler_pipeline_run_details")
        op.drop_table("crawler_pipeline_run_details")

    if "crawler_pipeline_runs" in inspector.get_table_names():
        op.drop_table("crawler_pipeline_runs")
