"""验证员工视图和权限配置

检查 employees 表和 employees_basic 视图是否存在且数据一致。
用于诊断 RAG 模式员工查询返回空结果的问题。
"""
import asyncio
from sqlalchemy import text
from common.persistence.database import get_session_factory


async def verify_views():
    """检查视图是否存在且有数据"""
    factory = get_session_factory()

    with factory() as session:
        print("\n" + "="*60)
        print("Employee Database View Verification")
        print("="*60 + "\n")

        # 检查 employees 完整表
        try:
            result = session.execute(text("SELECT COUNT(*) FROM employees"))
            count = result.scalar()
            print(f"[OK] employees table exists, record count: {count}")
        except Exception as e:
            print(f"[ERROR] employees table check failed: {e}")
            return

        # 检查 employees_basic 视图
        try:
            result = session.execute(text("SELECT COUNT(*) FROM employees_basic"))
            basic_count = result.scalar()
            print(f"[OK] employees_basic view exists, record count: {basic_count}")
        except Exception as e:
            print(f"[ERROR] employees_basic view check failed: {e}")
            print("\n[WARNING] Possible cause: view not created or definition is incorrect")
            return

        # 检查视图定义
        try:
            result = session.execute(text("""
                SELECT definition
                FROM pg_views
                WHERE schemaname = 'public' AND viewname = 'employees_basic'
            """))
            definition = result.scalar()
            if definition:
                print(f"\n[OK] employees_basic view definition:\n{definition}\n")
            else:
                print("\n[WARNING] employees_basic view definition not found")
        except Exception as e:
            print(f"\n[ERROR] Query view definition failed: {e}")

        # 检查视图字段列表
        try:
            result = session.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'employees_basic'
                ORDER BY ordinal_position
            """))
            columns = result.fetchall()
            print("[OK] employees_basic view columns:")
            for col_name, data_type in columns:
                print(f"  - {col_name}: {data_type}")
        except Exception as e:
            print(f"\n[ERROR] Query view columns failed: {e}")

        # 检查完整表字段列表（对比）
        try:
            result = session.execute(text("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'employees'
                ORDER BY ordinal_position
            """))
            columns = result.fetchall()
            print("\n[OK] employees table columns:")
            for col_name, data_type in columns:
                print(f"  - {col_name}: {data_type}")
        except Exception as e:
            print(f"\n[ERROR] Query table columns failed: {e}")

        # 验证视图是否包含 company_no（已废弃字段）
        try:
            result = session.execute(text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = 'employees_basic'
                AND column_name = 'company_no'
            """))
            has_company_no = result.fetchone() is not None

            print("\n" + "-"*60)
            if has_company_no:
                print("[WARNING] employees_basic view still contains deprecated company_no field")
                print("  This may cause RAG mode queries to fail")
                print("  Suggestion: Run 'alembic upgrade head' to update view definition")
            else:
                print("[OK] employees_basic view correctly removed company_no field")
        except Exception as e:
            print(f"\n[ERROR] Check company_no field failed: {e}")

        # 测试简单查询
        try:
            result = session.execute(text("""
                SELECT company_name, COUNT(*) as count
                FROM employees_basic
                GROUP BY company_name
                ORDER BY count DESC
                LIMIT 5
            """))
            companies = result.fetchall()
            print("\n[OK] Test query successful - Top 5 companies by employee count:")
            for company_name, emp_count in companies:
                print(f"  - {company_name}: {emp_count} employees")
        except Exception as e:
            print(f"\n[ERROR] Test query failed: {e}")
            print("  This may be the reason for RAG mode returning empty results")

        print("\n" + "="*60)
        print("Verification Complete")
        print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(verify_views())
