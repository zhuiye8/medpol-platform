# 医药政策动态采集平台（重构版）

该目录实现了“采集 → 格式化 → AI → 分发 → API/后台”的模块化架构，所有爬虫、任务与 AI 服务均可热插拔。核心文档：
- 架构蓝图：`docs/ARCHITECTURE_BLUEPRINT.md`
- 数据库准备：`docs/DB_SETUP.md`
- 公开接口：`docs/PUBLIC_API.md`
- 进度记录：`docs/PROGRESS_LOG.md`

## 环境准备

1. 复制配置并填写必要变量（同目录执行）  
   ```powershell
   copy .env.example .env
   ```
2. 安装依赖（默认使用 Conda `lhc`，也可自行决定虚拟环境）  
   ```powershell
   pip install -r requirements.txt
   ```
3. 升级数据库 Schema（**拉取新代码后务必执行**）  
   ```powershell
   alembic upgrade head
   ```
4. 如需运行 Playwright 爬虫：`python -m playwright install chromium`
5. 启动基础依赖与 Celery Worker（Windows 示例）  
   ```powershell
   $env:REDIS_URL="redis://localhost:6379/0"
   celery -A formatter_service.worker worker --loglevel=info --pool=solo -n formatter@%COMPUTERNAME% -Q formatter
   celery -A ai_processor.worker worker --loglevel=info --pool=solo -n ai@%COMPUTERNAME% -Q ai
   ```

## 快速体验

1. **初始化来源**（写入药渡云 / 医保局 / FDA / EMA / PMDA 等示例配置）  
   ```powershell
   python scripts/seed_sources.py
   ```
2. **运行爬虫**  
   ```powershell
   python scripts/run_crawlers.py
   ```
   - 默认涵盖药渡云 API/渲染、国家医保局、FDA 指南 & 新闻稿、EMA What's New、PMDA What's New
   - 若未配置数据库，将使用内置 fallback 配置
3. **执行 AI 任务**  
   ```powershell
   python scripts/run_ai_jobs.py
   ```
   - 仅负责入队，需确保 `ai_processor.worker` 正在运行
4. **启动 API 网关 + Admin Portal**  
   ```powershell
   uvicorn api_gateway.main:app --reload
   cd admin_portal
   pnpm install
   pnpm dev
   ```
   - Admin Portal 读取父目录 `.env` 中的 `VITE_API_BASE_URL`、`LOG_FILE_PATH`、`ADMIN_PORTAL_ORIGINS`
5. **分发 / 调度辅助脚本**  
   - `python scripts/run_distribution.py`：将 formatter 结果写入缓存 / webhook stub  
   - `python scripts/run_scheduler.py`：轮询数据库中的 `crawler_jobs` 执行计划任务  
   - `python scripts/reset_data.py`：清空数据（需配置 `DATABASE_URL` + `REDIS_URL`）

## 测试

```powershell
python -m pytest
```

## 目录速览

- `crawler_service/`：BaseCrawler、调度器、示例爬虫（药渡云、医保局、FDA、EMA、PMDA 等）
- `formatter_service/`：Celery worker，负责去重、清洗、入库
- `ai_processor/`：AI 摘要/翻译/分析任务（OpenAI / DeepSeek / Mock）
- `distribution_service/`：缓存与 webhook stub
- `scheduler_service/`：调度 API、任务配置与运行记录
- `api_gateway/`：FastAPI，公开 `/v1/articles`、调度与健康检查接口
- `admin_portal/`：pnpm + React 后台（文章列表、详情、调度、日志）
- `scripts/`：一键命令（seed、crawl、AI、distribution、scheduler 等）
- `docs/`：蓝图、开放接口、进度、DB 说明
- `sample_data/`：本地 outbox/normalized/cache 示例

> 运行任何命令前请确保设置必要环境变量（PowerShell 示例）：
> ```powershell
> $env:DATABASE_URL="postgresql+psycopg://medpol:medpol@localhost:5432/medpol"
> $env:REDIS_URL="redis://localhost:6379/0"
> $env:PYTHONUTF8="1"
> ```
