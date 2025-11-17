# 数据库与迁移指引

## 一次性准备

1. 启动基础服务：
   ```bash
   make infra-up
   ```
2. 设置 `DATABASE_URL`（or 编辑 `.env`）：
   ```
   postgresql+psycopg://medpol:medpol@localhost:5432/medpol
   ```
3. 初始化数据库（若首次）：
   ```bash
   alembic upgrade head
   ```

> `alembic.ini` 已预置，迁移文件位于 `migrations/versions/`。

## 更新流程

1. 修改 `common/persistence/models.py`
2. 生成迁移脚本：
   ```bash
   alembic revision --autogenerate -m "describe change"
   ```
3. 审核 `migrations/versions/*.py`
4. 应用：
   ```bash
   alembic upgrade head
   ```

## 常见问题

- **提示缺少 DATABASE_URL**：确保 `.env` 中存在该变量，并在运行命令前 `set DATABASE_URL=...`。
- **表不存在**：确认已执行 `alembic upgrade head`，或在 `infra` 中启动 PostgreSQL 容器。
