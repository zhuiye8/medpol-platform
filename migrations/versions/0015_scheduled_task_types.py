"""add task_type to crawler_jobs for non-crawler scheduled tasks"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0015_scheduled_task_types"
down_revision = "0014_employee_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add task_type column with default 'crawler' for existing jobs
    op.add_column(
        "crawler_jobs",
        sa.Column(
            "task_type",
            sa.String(length=32),
            nullable=False,
            server_default="crawler",
        ),
    )

    # Make source_id nullable (non-crawler tasks don't need it)
    op.alter_column(
        "crawler_jobs",
        "source_id",
        existing_type=sa.String(length=36),
        nullable=True,
    )

    # Make crawler_name nullable (non-crawler tasks don't need it)
    op.alter_column(
        "crawler_jobs",
        "crawler_name",
        existing_type=sa.String(length=128),
        nullable=True,
    )


def downgrade() -> None:
    # Make crawler_name non-nullable again
    op.alter_column(
        "crawler_jobs",
        "crawler_name",
        existing_type=sa.String(length=128),
        nullable=False,
    )

    # Make source_id non-nullable again
    op.alter_column(
        "crawler_jobs",
        "source_id",
        existing_type=sa.String(length=36),
        nullable=False,
    )

    # Drop task_type column
    op.drop_column("crawler_jobs", "task_type")
