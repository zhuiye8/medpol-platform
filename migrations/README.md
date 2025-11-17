# 数据库迁移计划

当前阶段只提供 ORM 定义，后续将使用 Alembic 维护迁移脚本。建议流程：

1. 在根目录运行 `alembic init migrations`（一次性操作）
2. 编辑 `alembic.ini`，让 `sqlalchemy.url` 读取 `.env` 中的 `DATABASE_URL`
3. 在 `migrations/env.py` 中导入 `common.persistence.models.Base`
4. 使用 `alembic revision --autogenerate -m "init schema"` 生成首个迁移
5. 通过 `alembic upgrade head` 应用

> 目前此目录仅作为占位，便于跟踪迁移历史。
