"""add conversation_sessions for chat memory"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0006_conversation_sessions"
down_revision = "0005_finance_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_sessions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("persona", sa.String(length=32), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("messages_json", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("conversation_sessions")
