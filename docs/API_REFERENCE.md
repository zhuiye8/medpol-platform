# API 接口文档（v0.1）

> 当前 Admin Portal 与上游系统依赖的 FastAPI 服务入口 `http://localhost:8000`。所有响应均采用统一 Envelope 结构：`{ "code": 0, "msg": "success", "data": <payload> }`。异常时会返回非 0 `code` 与 `detail` 字段。

## 1. 健康检查

- **URL**：`GET /healthz`
- **用途**：基础探活，供运维/监控以及 Admin Portal 状态指示器使用。
- **Query**：无
- **响应体**
  ```json
  {
    "code": 0,
    "msg": "success",
    "data": {
      "status": "ok"
    }
  }
  ```

## 2. 查询文章列表

- **URL**：`GET /v1/articles/`
- **用途**：为 Admin Portal、公开 API 或下游业务提供最新标准化文章。支持分页与分类过滤，暂按更新时间倒序。
- **Query 参数**
  | 参数 | 类型 | 默认 | 说明 |
  | --- | --- | --- | --- |
  | `page` | `int` | 1 | 页码，起始 1 |
  | `page_size` | `int` | 20 | 每页条数，范围 1～100 |
| `category` | `str` | `null` | 可选，按业务分类过滤（例如 `frontier`） |

- 分类枚举（`category` 参数与响应字段共享）：  
  | 枚举值 | 中文含义 |
  | --- | --- |
  | `frontier` | 前沿动态 |
  | `fda_policy` | FDA 政策 |
  | `ema_policy` | EMA 政策 |
  | `pmda_policy` | PMDA 政策 |
  | `project_apply` | 项目申报 |
- **响应体**
  ```json
  {
    "code": 0,
    "msg": "success",
    "data": {
      "items": [
        {
          "id": "art-demo",
          "title": "示例标题",
          "summary": "AI 摘要",
          "publish_time": "2025-01-01T00:00:00Z",
          "source_name": "药渡云",
          "category": "frontier",
          "tags": ["药渡云", "前沿动态"],
          "source_url": "https://example.com/article"
        }
      ],
      "page": 1,
      "page_size": 20,
      "total": 1
    }
  }
  ```
- **说明**
  - 目前 `total` 为当前返回条数，后续支持真实分页统计。
  - 若希望查询特定来源，可在上游调用时约定分类值。

### 2.1 查询文章详情

- **URL**：`GET /v1/articles/{article_id}`
- **返回字段**
  - `content_html`：原文 HTML
  - `translated_content` / `translated_content_html`：AI 翻译后的纯文本与 HTML（若原文非中文）
  - `ai_analysis`：结构化分析（key_points/risks/actions 等）
  - `ai_results`：模型调用记录（摘要、翻译、分析等）
  - `original_source_language`：检测到的原文语言

## 3. 读取运行日志（后台）

- **URL**：`GET /v1/admin/logs`
- **用途**：Admin Portal 日志页面，读取 `.env` 中 `LOG_FILE_PATH` 配置的文件尾部内容，帮助排查爬虫/AI/分发执行情况。
- **Query 参数**
  | 参数 | 类型 | 默认 | 说明 |
  | --- | --- | --- | --- |
  | `limit` | `int` | 200 | 返回日志行数，范围 10～2000 |
- **响应体**
  ```json
  {
    "code": 0,
    "msg": "success",
    "data": {
      "lines": [
        { "idx": 123, "content": "INFO ... run_crawlers OK" },
        { "idx": 124, "content": "INFO ... formatter saved 10 rows" }
      ],
      "total": 1024,
      "truncated": true
    }
  }
  ```
- **说明**
  - 若日志文件不存在或读取失败，将返回空数组 + `total: 0`。
  - 默认放行 `http://localhost:4173` 来源；可通过 `ADMIN_PORTAL_ORIGINS` 扩展。

## 4. 调度管理（Crawler Jobs）

- **列出可用爬虫**：`GET /v1/crawlers/meta`
- **任务 CRUD**：
  - `GET /v1/crawler-jobs`
  - `POST /v1/crawler-jobs` （字段：`name`、`crawler_name`、`source_id`、`job_type`、`interval_minutes`/`schedule_cron`、`payload`、`enabled`）
  - `PATCH /v1/crawler-jobs/{id}`
- **执行与历史**：
  - `POST /v1/crawler-jobs/{id}/run`（可传 `payload_override` 触发一次临时测试）
  - `GET /v1/crawler-jobs/{id}/runs`
- **说明**
  - `payload.meta` 会被注入到爬虫配置，可用于覆盖 `max_pages`、`page_size` 等参数
  - Admin Portal 的“任务调度”页面基于以上接口实现
  - 后台脚本 `python scripts/run_scheduler.py` 会定期扫描 `crawler_jobs`，对启用的定时任务执行采集

## 环境变量汇总

| 变量 | 说明 |
| --- | --- |
| `DATABASE_URL` | SQLAlchemy DSN，供 API 查询与脚本使用 |
| `REDIS_URL` | 缓存/队列地址（当前用于 outbox 与调度） |
| `LOG_FILE_PATH` | `/v1/admin/logs` 查看的日志路径 |
| `VITE_API_BASE_URL` | Admin Portal 请求 API 的基础地址 |
| `ADMIN_PORTAL_ORIGINS` | 允许跨域的前端地址，逗号分隔 |

## 下一阶段公开接口规划

| 接口目标 | 路径草案 | 功能要点 |
| --- | --- | --- |
| 文章详情 | `GET /v1/articles/{article_id}` | 根据主键返回完整内容（HTML + text + metadata） |
| AI 结果查询 | `GET /v1/articles/{id}/ai-results` | 返回摘要/翻译/分析各任务的最新输出 |
| 分页游标接口 | `GET /v1/articles/stream` | 支持 `since` 或 `cursor` 参数，供数据分发消费 |
| 源站配置查询 | `GET /v1/sources` | 暴露启用的来源与类别，便于前端筛选 |
| 调度状态查询 | `GET /v1/crawlers/status` | 展示各爬虫运行状况，供后台与监控 |

后续开发会围绕上述接口展开，确保对外提供稳定的数据消费能力，并逐步拆分后台专用与公开 API 的权限及限流策略。
