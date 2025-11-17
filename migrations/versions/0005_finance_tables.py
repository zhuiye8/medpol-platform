"""finance tables"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0005_finance_tables"
down_revision = "0004_article_translation_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finance_sync_logs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default=sa.text("'finance_api'")),
        sa.Column("mode", sa.String(length=32), nullable=False, server_default=sa.text("'full'")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("inserted_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "finance_records",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("sync_log_id", sa.String(length=64), nullable=True),
        sa.Column("keep_date", sa.Date(), nullable=False),
        sa.Column("type_no", sa.String(length=8), nullable=False),
        sa.Column("type_name", sa.String(length=64), nullable=True),
        sa.Column("company_no", sa.String(length=64), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=True),
        sa.Column("company_name", sa.String(length=128), nullable=True),
        sa.Column("high_company_no", sa.String(length=64), nullable=True),
        sa.Column("level", sa.String(length=16), nullable=True),
        sa.Column("current_amount", sa.Numeric(20, 4), nullable=True),
        sa.Column("last_year_amount", sa.Numeric(20, 4), nullable=True),
        sa.Column("last_year_total_amount", sa.Numeric(20, 4), nullable=True),
        sa.Column("this_year_total_amount", sa.Numeric(20, 4), nullable=True),
        sa.Column("add_amount", sa.Numeric(20, 4), nullable=True),
        sa.Column("add_rate", sa.Numeric(10, 4), nullable=True),
        sa.Column("year_add_amount", sa.Numeric(20, 4), nullable=True),
        sa.Column("year_add_rate", sa.Numeric(10, 4), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint([
            "sync_log_id"
        ], [
            "finance_sync_logs.id"
        ], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_finance_records_keep_date", "finance_records", ["keep_date"])
    op.create_index("ix_finance_records_type_no", "finance_records", ["type_no"])
    op.create_index("ix_finance_records_company_no", "finance_records", ["company_no"])


def downgrade() -> None:
    op.drop_index("ix_finance_records_company_no", table_name="finance_records")
    op.drop_index("ix_finance_records_type_no", table_name="finance_records")
    op.drop_index("ix_finance_records_keep_date", table_name="finance_records")
    op.drop_table("finance_records")
    op.drop_table("finance_sync_logs")
