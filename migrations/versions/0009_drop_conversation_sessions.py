"""drop legacy conversation_sessions table"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "0009_drop_conversation_sessions"
down_revision = "0008_pipeline_runs_and_retry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP TABLE IF EXISTS conversation_sessions")


def downgrade() -> None:
    # 恢复表结构以便回滚
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS conversation_sessions (
            id VARCHAR(64) PRIMARY KEY,
            persona VARCHAR(32),
            summary TEXT NOT NULL DEFAULT '',
            messages_json JSON NOT NULL DEFAULT '[]',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
