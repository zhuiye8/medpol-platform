# 团队协作指南（Codex CLI）

> 供新同事快速了解目录结构、流程与注意事项。

## 1. 环境

- 仓库：`C:\work\lianhuan\medpol-platform`
- Python：Conda `lhc`（3.10.19）。激活后执行：
  ```powershell
  pip install -r requirements.txt
  python -m playwright install chromium   # 如需 Playwright
  ```
- 必要变量（PowerShell）：
  ```powershell
  $env:DATABASE_URL="postgresql+psycopg://medpol:medpol@localhost:5432/medpol"
  $env:REDIS_URL="redis://localhost:6379/0"
  $env:PYTHONUTF8="1"
  ```
- 初始化：
  ```powershell
  alembic upgrade head
  python scripts/seed_sources.py
  ```

## 2. 目录职责

| 目录 | 说明 |
| --- | --- |
| `crawler_service/` | `base.py`（基类）、`registry.py`、`scheduler.py`、各来源爬虫 |
| `formatter_service/` | Celery worker，文本清洗、去重、入库 |
| `ai_processor/` | AI 任务扫描、worker、提示词 |
| `distribution_service/` | 分发 stub（缓存+webhook） |
| `scheduler_service/` | 调度 API（任务/执行记录） |
| `api_gateway/` | FastAPI `/v1/articles`、调度、健康检查 |
| `admin_portal/` | React + pnpm 后台管理 |
| `scripts/` | 常用脚本（crawl/ai/distribution/reset 等） |
| `docs/` | 蓝图、公开 API、进度、本指南 |
| `tests/` | pytest 用例（formatter、API） |

## 3. 常用命令

```powershell
python scripts/run_crawlers.py
python scripts/run_ai_jobs.py
python scripts/process_outbox.py
python scripts/run_distribution.py
python scripts/run_scheduler.py
python scripts/reset_data.py
uvicorn api_gateway.main:app --reload
cd admin_portal; pnpm dev
python -m pytest
```

## 4. 爬虫开发

1. 在 `crawler_service/crawlers/` 新建文件，继承 `BaseCrawler`，实现 `crawl/parse/_build_result`。
2. 填写 `name`、`label`、`category`（`common/domain/models.py` 的 `ArticleCategory`），构造 `CrawlResult`。
3. 文件末尾 `registry.register(MyCrawler)`。
4. 在 `scripts/seed_sources.py` 增加来源，并在 `crawler_service/scheduler.py` 的 `DEFAULT_CONFIGS` 里放一个默认配置。
5. 运行 `python scripts/run_crawlers.py` 验证输出；Admin Portal 调度页会自动识别。

## 5. Formatter / AI / Distribution

- Formatter 入口：`formatter_service/worker.py`；映射与清洗在 `rules.py`、`utils.py`。
- AI 任务：`ai_processor/batch.py`（扫描）、`ai_processor/worker.py`（执行），LLM 供应商由 `.env` 控制。
- Distribution：`distribution_service/service.py` + `worker.py`，目前写入缓存与 webhook，可在此扩展。

## 6. API 与前端

- 公共接口详见 `docs/PUBLIC_API.md`，新增字段需同步文档与 `admin_portal`。
- FastAPI CORS 默认 `allow_origins=["*"]`，若要限制请设置 `ADMIN_PORTAL_ORIGINS`。
- Admin Portal 读取父级 `.env` 中的 `VITE_API_BASE`、`LOG_FILE_PATH`。

## 7. 数据迁移

- 现有迁移：`0001`~`0004`。如需新增字段，执行 `alembic revision --autogenerate -m "desc"`，文件存于 `migrations/versions/`。
- 尚无生产数据，必要时可以 drop/recreate DB 后重新 `alembic upgrade head`。

## 8. 规范

- 注释用中文，说明“意图/原因”。
- 代码提交前运行 `python -m pytest`。
- 新功能请在 `docs/PROGRESS_LOG.md` 记录要点，便于跟踪。
- 使用 Codex CLI 时保持根目录命令，避免再次生成仓外目录。

## 9. FAQ

- **运行管线无数据**：确认 formatter/ai Celery worker 均在线，Redis/DB 变量已设。
  ```powershell
  celery -A formatter_service.worker worker --loglevel=info --pool=solo -n formatter@%COMPUTERNAME% -Q formatter
  celery -A ai_processor.worker worker --loglevel=info --pool=solo -n ai@%COMPUTERNAME% -Q ai
  ```
- **AI 结果少**：可能去重状态未清；执行 `python scripts/reset_data.py` 并重启 worker。
- **PDF 站点**：当前策略是跳过或输出链接，待统一 PDF 解析方案上线再补全。

如有疑问，可在 Codex CLI 直接 `rg` 检索或查阅 `docs/` 目录。祝开发顺利！
- Docker（可选）：如果希望在 Windows 上快速启动 DB/Redis，可运行：
  ```powershell
  docker compose -f infra\docker-compose.yml up -d
  ```
- 常态部署（本地可运行）：
  ```powershell
  # 1. 启动数据库/Redis（Docker 或本地服务）
  docker compose -f infra\docker-compose.yml up -d

  # 2. 激活环境、启动 Celery Worker
  conda activate lhc
  $env:DATABASE_URL="postgresql+psycopg://medpol:medpol@localhost:5432/medpol"
  $env:REDIS_URL="redis://localhost:6379/0"
  celery -A formatter_service.worker worker --loglevel=info --pool=solo -n formatter@%COMPUTERNAME% -Q formatter
  celery -A ai_processor.worker worker --loglevel=info --pool=solo -n ai@%COMPUTERNAME% -Q ai

  # 3. 启动 API 与 Admin Portal（另开 PowerShell 终端）
  uvicorn api_gateway.main:app --reload
  cd admin_portal; pnpm install; pnpm dev

  # 4. 手动执行一遍管线验证
  python scripts/seed_sources.py
  python scripts/run_crawlers.py
  python scripts/run_ai_jobs.py
  python scripts/run_distribution.py
  ```
- 这样即可在浏览器访问：
  - API: `http://localhost:8000/v1/articles`
  - Admin Portal: `http://localhost:4173`（代理到 API）
