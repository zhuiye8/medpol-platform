"""drop employee company_no field and add company_name index"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0016_drop_employee_company_no"
down_revision = "0015_scheduled_task_types"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop views first (they depend on company_no)
    op.execute("DROP VIEW IF EXISTS employees_basic")
    op.execute("DROP VIEW IF EXISTS employees_full")

    # 2. Check and drop index if exists
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {idx["name"] for idx in inspector.get_indexes("employees")}

    if "ix_employees_company_no" in indexes:
        op.drop_index("ix_employees_company_no", table_name="employees")

    # 3. Drop company_no column
    op.drop_column("employees", "company_no")

    # 4. Add company_name index for better query performance
    op.create_index("ix_employees_company_name", "employees", ["company_name"])

    # 5. Recreate views without company_no

    op.execute("""
        CREATE VIEW employees_basic AS
        SELECT
            id, company_name, name, gender,
            department, position, employee_level, is_contract,
            highest_education, graduate_school, major,
            political_status, professional_title, skill_level,
            hire_date, created_at, updated_at
        FROM employees;
    """)

    op.execute("""
        CREATE VIEW employees_full AS
        SELECT * FROM employees;
    """)


def downgrade() -> None:
    # 1. Drop views
    op.execute("DROP VIEW IF EXISTS employees_basic")
    op.execute("DROP VIEW IF EXISTS employees_full")

    # 2. Drop company_name index
    op.drop_index("ix_employees_company_name", table_name="employees")

    # 3. Add company_no column back (nullable to avoid rollback failures)
    op.add_column(
        "employees",
        sa.Column("company_no", sa.String(length=32), nullable=True)
    )

    # 4. Create index for company_no
    op.create_index("ix_employees_company_no", "employees", ["company_no"])

    # 5. Recreate original views
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

    op.execute("""
        CREATE VIEW employees_full AS
        SELECT * FROM employees;
    """)
