"""auth tables - users, roles, user_roles"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0013_auth_tables"
down_revision = "0012_article_embeddings_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 用户表
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=256), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("email", sa.String(length=128), nullable=True),
        sa.Column("company_no", sa.String(length=32), nullable=True),  # 所属公司（可选）
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_company_no", "users", ["company_no"])

    # 角色表
    op.create_table(
        "roles",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=256), nullable=True),
        sa.Column("permissions", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_roles_name", "roles", ["name"])

    # 用户-角色关联表
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("role_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "role_id"),
    )

    # 预置角色
    op.execute("""
        INSERT INTO roles (id, name, description, permissions) VALUES
        ('role-admin', 'admin', '系统管理员，拥有全部权限', '{"employee": "full", "finance": true, "policy": true}'::jsonb),
        ('role-hr-manager', 'hr_manager', '人力资源经理，可查看员工全部信息', '{"employee": "full", "finance": false, "policy": true}'::jsonb),
        ('role-hr-viewer', 'hr_viewer', '人力资源查看者，只能查看员工基本信息', '{"employee": "basic", "finance": false, "policy": true}'::jsonb),
        ('role-finance', 'finance', '财务人员，可查询财务数据', '{"employee": false, "finance": true, "policy": true}'::jsonb),
        ('role-viewer', 'viewer', '普通查看者，只能检索政策', '{"employee": false, "finance": false, "policy": true}'::jsonb)
    """)

    # 预置管理员账号 (密码: admin123，使用 bcrypt 哈希)
    # 哈希值: $2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.SXqo4J.HXH3Mwe
    op.execute("""
        INSERT INTO users (id, username, password_hash, display_name, is_active) VALUES
        ('user-admin', 'admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.SXqo4J.HXH3Mwe', '系统管理员', true)
    """)

    # 给管理员分配 admin 角色
    op.execute("""
        INSERT INTO user_roles (user_id, role_id) VALUES
        ('user-admin', 'role-admin')
    """)


def downgrade() -> None:
    op.drop_table("user_roles")
    op.drop_index("ix_roles_name", table_name="roles")
    op.drop_table("roles")
    op.drop_index("ix_users_company_no", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
