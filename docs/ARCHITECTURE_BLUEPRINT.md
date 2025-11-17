# 医药政策动态采集平台架构蓝图

## 目标
- 统一“采集 → 格式化 → AI 加工 → 分发 → API/后台”流水线，保证模块热插拔与横向扩展。
- 用清晰的数据与错误码契约连接各模块，降低任一环节替换成本。
- 通过 Celery + Redis（可替换 Kafka/NATS 等）承载异步任务，Playwright + 可插拔爬虫覆盖政策/新闻源。
- AI 层原生支持 OpenAI / DeepSeek，并可扩展到自研/其他模型，满足翻译与专业解读需求。

## 顶层目录

```
medpol-platform/
  docs/                     # 设计、API、运维文档
  infra/                    # docker-compose、Helm、监控、Playwright 镜像、CI 脚本
  scripts/                  # 开发脚本、脚手架、Smoke Test
  common/                   # 公共领域模型、客户端、消息、存储抽象
  crawler_service/          # 采集模块
  formatter_service/        # 格式化与去重模块
  ai_processor/             # AI 处理流水线
  distribution_service/     # 数据落库与多渠道分发
  api_gateway/              # FastAPI 接口网关
  admin_portal/             # 后台前端（React/Vue）
```

## 模块职责

### common
- `domain/`：Pydantic 数据模型（Article、AIResult、Source、Task、ErrorEnvelope 等），字段遵守 snake_case。
- `clients/`：HTTP、Playwright、LLM Provider 封装；`clients/llm` 负责 OpenAI/DeepSeek 调度与鉴权。
- `messaging/`：事件 Schema、Redis Stream/Kafka 封装、重试与死信策略。
- `persistence/`：SQLAlchemy 模型、仓储接口、迁移脚本，包含 `articles`、`ai_results`、`sources`、`delivery_logs` 等表。
- `utils/`：日志（结构化 JSON）、配置装载、追踪。

### crawler_service
- `BaseCrawler` 约定 `name/label/start_urls/crawl/parse`，统一日志、异常、重试。
- 插件注册：支持 YAML/DB 描述（频率、鉴权、标签），运行时动态加载，真正实现热插拔。
- 采集结果写入 `raw_article` 事件，包含 `source_url/content_html/meta` 等字段。
- 监控 Playwright/HTTP 资源占用，合规遵循 robots.txt、请求频率、UA/代理策略。

### formatter_service
- 订阅 `raw_article`，执行字段映射、HTML 清洗、标签聚合、去重（URL + 内容哈希）。
- 按文档标准生成结构化文章，写入数据库并推送 `needs_ai` 事件。
- 管理字段缺失、格式异常、重复数据的告警与补录机制。

### ai_processor
- Celery Worker 读取 `needs_ai`，串行/并行执行摘要、翻译、专业解读等任务链。
- `providers/` 封装 OpenAI、DeepSeek，支持主备/按任务选择策略。
- 结果写入 `ai_results` 并发布 `distribution_event`，附带 provider、模型、耗时、重试记录。
- 支持 Mock Provider 以便无 Key 环境运行。

### distribution_service
- 接收 `distribution_event` 与 `article_upsert` 事件，写入 PostgreSQL/ElasticSearch/Cache。
- Webhook、消息队列、订阅推送统一在此模块实现，支持标签/分类/时间过滤。
- 记录分发日志、重试、回调状态，并暴露健康指标。

### api_gateway
- 基于 FastAPI，分离公开 API 与管理 API，统一响应壳 `{code,msg,data}` 与错误码区间。
- 负责鉴权、速率限制、分页/筛选、Webhook Token 校验。
- 通过依赖注入调用 `common.persistence` 与 `common.messaging`，而非直接操作其它模块。

### admin_portal
- 提供任务/日志/告警可视化，支持配置爬虫（频率、代理、凭证）、AI 策略、Webhook。
- 仅调用 `api_gateway`，不直接访问后台服务。

## 事件流
1. `crawler_service` 采集内容 → 发布 `raw_article`.
2. `formatter_service` 消费 `raw_article` → 清洗写库 → 发布 `needs_ai`.
3. `ai_processor` 消费 `needs_ai` → 产生 AI 结果 → 发布 `distribution_event`.
4. `distribution_service` 消费 `distribution_event` → 写入多种数据存储并触发 Webhook/MQ.
5. `api_gateway` 查询数据库/缓存，`admin_portal` 通过 API 控制调度与配置。

所有事件默认使用 Redis Streams，Topic 与 Schema 统一登记在 `docs/events.md`，未来可切换 Kafka/NATS。

## AI Provider 设计
- `LLMProvider` 抽象定义 `summarize`, `translate`, `analyze` 等方法，统一入参/出参与异常。
- `provider_router` 读取 `.env` 中的 `AI_PRIMARY`, `AI_FALLBACK`，支持 per-task override。
- OpenAI/DeepSeek 的 Key 与 Base URL 由配置中心注入，可扩展多账户轮询与速率控制。
- Provider 层负责异常归一化（网络/鉴权/额度/内容风控等），与错误码体系联动。

## 基础设施与 DevEx
- `infra/` 维护 docker-compose（Redis、PostgreSQL、Playwright、Celery Flower、Prometheus/Grafana）。
- 提供 `make`/`Invoke` 脚本：`make start`, `make seed_sources`, `make smoke`.
- Playwright 浏览器、OpenTelemetry、结构化日志、Tracing、告警策略统一在此目录定义。

## 迁移策略
1. **Schema 对齐**：把现有 demo 的数据库模型迁移到 `common/persistence`，保证旧 API 可继续使用。
2. **Formatter MVP**：拆出 `formatter_service` 接管数据清洗，确保标准字段输出。
3. **Crawler 插件化**：逐个把旧爬虫迁到 `crawler_service/crawlers/*`，验证动态注册。
4. **AI 双 Provider**：实现 OpenAI/DeepSeek Provider 与 Router，建立 smoke test。
5. **Distribution/API 重写**：新 `api_gateway` 与 `distribution_service` 上线后，逐步切断旧 backend 依赖。

## 下一步
- 完成 `common` 包的模型、配置、消息封装与单元测试。
- 实现 `crawler_service` 的 BaseCrawler 抽象 + 注册机制 + 示例爬虫。
- 编写 `formatter_service` 与 `ai_processor` 的 Celery 工作流骨架，引入 Provider Router。
- 在 CI 中运行静态检查（ruff/black）、类型检查（mypy）与 smoke test。
