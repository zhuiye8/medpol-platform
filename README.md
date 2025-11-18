医药政策动态采集平台（重构版）

本项目实现“采集→格式化→AI→分发→API/后台”的模块化架构，所有采集/扩展与 AI 服务可热插拔。参考：docs/ARCHITECTURE_BLUEPRINT.md、docs/DB_SETUP.md、docs/PUBLIC_API.md、docs/PROGRESS_LOG.md。

## 环境准备
1) 复制环境配置
```powershell
copy .env.example .env
```
2) 启动基础服务（Postgres/Redis）
```powershell
docker compose -f infra/docker-compose.yml up -d postgres redis
```
3) 安装依赖
```powershell
pip install -r requirements.txt
```
4) 初始化数据库 Schema（拉新代码后必须执行）
```powershell
alembic upgrade head
```
5) 安装 Playwright 依赖（若需采集）
```powershell
python -m playwright install chromium
```
6) 启动 Celery Worker（Windows 示例）
```powershell
$env:PYTHONUTF8="1"
$env:DATABASE_URL="postgresql+psycopg://medpol:medpol@localhost:5432/medpol"
$env:REDIS_URL="redis://localhost:6379/0"
celery -A formatter_service.worker worker --loglevel=info --pool=solo -n formatter@%COMPUTERNAME% -Q formatter
celery -A ai_processor.worker worker --loglevel=info --pool=solo -n ai@%COMPUTERNAME% -Q ai
```

## 快速体验
1) 初始化来源
```powershell
python scripts/seed_sources.py
```
2) 运行采集
```powershell
python scripts/run_crawlers.py
```
3) 执行 AI 任务
```powershell
python scripts/run_ai_jobs.py
```
4) 启动 API 网关 + Admin Portal
```powershell
uvicorn api_gateway.main:app --reload
cd admin_portal
pnpm install
pnpm dev
```
5) 其他脚本
- `python scripts/run_distribution.py`：分发缓存/webhook stub
- `python scripts/run_scheduler.py`：执行 crawler_jobs
- `python scripts/sync_finance_data.py --month 2024-09`：拉财务数据入库（不带 month 为全量）
- `python scripts/reset_data.py`：清空数据（需 DATABASE_URL + REDIS_URL）

## 测试
```powershell
python -m pytest
```

## 目录速览
- crawler_service：BaseCrawler、调度器、示例爬虫（药渡云、医保局、FDA、EMA、PMDA）
- formatter_service：Celery 去重/清洗/入库
- ai_processor：AI 摘要/翻译/分析任务
- distribution_service：缓存与 webhook stub
- scheduler_service：调度 API、任务配置与执行记录
- api_gateway：FastAPI，公开 /v1/articles 等
- admin_portal：pnpm + React 后台（列表/详情/调度/日志）
- scripts：seed、crawl、AI、distribution、scheduler、finance sync、reset
- docs：架构、接口、进度、DB 说明
- sample_data：outbox/normalized/cache 示例

> 运行前请设置必要环境变量（PowerShell 示例）：
> ```powershell
> $env:DATABASE_URL="postgresql+psycopg://medpol:medpol@localhost:5432/medpol"
> $env:REDIS_URL="redis://localhost:6379/0"
> $env:PYTHONUTF8="1"
> ```
