"""employee table with permission views"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0014_employee_table"
down_revision = "0013_auth_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 员工表
    op.create_table(
        "employees",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("company_no", sa.String(length=32), nullable=False),  # 公司编号（如 ydjyhb）
        sa.Column("company_name", sa.String(length=128), nullable=True),  # 公司名称
        sa.Column("name", sa.String(length=64), nullable=False),  # 姓名
        sa.Column("gender", sa.String(length=8), nullable=True),  # 性别
        sa.Column("id_number", sa.String(length=32), nullable=True),  # 身份证号（敏感）
        sa.Column("phone", sa.String(length=32), nullable=True),  # 电话号码（敏感）
        sa.Column("department", sa.String(length=128), nullable=True),  # 部门
        sa.Column("position", sa.String(length=128), nullable=True),  # 职务
        sa.Column("employee_level", sa.String(length=32), nullable=True),  # 员工级别（一般员工/中层/管理层）
        sa.Column("is_contract", sa.Boolean(), nullable=True),  # 是否合同工（可选）
        sa.Column("highest_education", sa.String(length=32), nullable=True),  # 最高学历
        sa.Column("graduate_school", sa.String(length=128), nullable=True),  # 毕业院校
        sa.Column("major", sa.String(length=128), nullable=True),  # 专业
        sa.Column("political_status", sa.String(length=32), nullable=True),  # 政治面貌
        sa.Column("professional_title", sa.String(length=64), nullable=True),  # 职称
        sa.Column("skill_level", sa.String(length=32), nullable=True),  # 技能等级
        sa.Column("hire_date", sa.Date(), nullable=True),  # 入职时间
        sa.Column("raw_data", sa.JSON(), nullable=False, server_default=sa.text("'{}'::jsonb")),  # 原始数据备份
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 索引
    op.create_index("ix_employees_company_no", "employees", ["company_no"])
    op.create_index("ix_employees_name", "employees", ["name"])
    op.create_index("ix_employees_department", "employees", ["department"])
    op.create_index("ix_employees_position", "employees", ["position"])
    op.create_index("ix_employees_employee_level", "employees", ["employee_level"])

    # 基础视图（不含敏感字段：id_number, phone）
    # hr_viewer 及以下角色使用此视图
    op.execute("""
        CREATE VIEW employees_basic AS
        SELECT
            id, company_no, company_name, name, gender,
            department, position, employee_level, is_contract,
            highest_education, graduate_school, major,
            political_status, professional_title, skill_level,
            hire_date, created_at, updated_at
        FROM employees;
    """)

    # 完整视图（包含全部字段）
    # hr_manager 及 admin 角色使用此视图
    op.execute("""
        CREATE VIEW employees_full AS
        SELECT * FROM employees;
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS employees_full;")
    op.execute("DROP VIEW IF EXISTS employees_basic;")
    op.drop_index("ix_employees_employee_level", table_name="employees")
    op.drop_index("ix_employees_position", table_name="employees")
    op.drop_index("ix_employees_department", table_name="employees")
    op.drop_index("ix_employees_name", table_name="employees")
    op.drop_index("ix_employees_company_no", table_name="employees")
    op.drop_table("employees")
