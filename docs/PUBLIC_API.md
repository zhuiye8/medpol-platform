# 公开 API 文档

> 基础域名：`http://101.132.130.146:8000`。所有接口统一返回壳：
> ```json
> { "code": 0, "msg": "success", "data": { ... } }
> ```

## 分类枚举

| 枚举值 | 说明 |
| --- | --- |
| `frontier` | 前沿动态 |
| `bidding` | 医保招标采集（国家/省级集中采购） |
| `laws` | 法律法规（CDE） |
| `institution` | 中心制度（CDE） |
| `cde_trend` | CDE 动态（国家医保局 政策与动态） |
| `industry_trend` | 行业动态（国家医保局 地方工作动态） |
| `project_apply` | 项目申报 |
| `fda_policy` | FDA 政策 |
| `ema_policy` | EMA 政策 |
| `pmda_policy` | PMDA 政策 |

通用字段：`content_html`、`translated_content`/`translated_content_html`、`summary`、`ai_analysis`、`ai_results`（task_type: summary/translation/analysis），分页参数 `page`(>=1)/`page_size`(1-100)，时间字段为 ISO8601。

## 文章列表/详情

- 列表：`GET /v1/articles/?category={category}&page=1&page_size=20`
  - 返回字段：id/title/summary/publish_time/source_name/category/tags/source_url/apply_status/is_positive_policy
  - 额外 `stats` 字段（只在特定分类返回）：
    - FDA/EMA/PMDA：`{ "total_count": 总数, "year_count": 当年数, "positive_count": 利好政策数 }`
    - 项目申报：`{ "pending_total", "pending_year", "submitted_total", "submitted_year" }`
    - 其他分类 `stats` 为 null
- 详情：`GET /v1/articles/{article_id}`（正文+翻译+ai_analysis+apply_status+is_positive_policy+ai_results）
- 健康检查：`GET /healthz`

## 分类说明与补充接口

- 前沿动态：`category=frontier`
- 医保招标采集：`category=bidding`
- 法律法规：`category=laws`
- 中心制度：`category=institution`
- CDE 动态：`category=cde_trend`
- 行业动态：`category=industry_trend`
- 项目申报：`category=project_apply`
  - 统计：`GET /v1/articles/stats/project_apply`
  - 更新状态：`POST /v1/articles/project_apply/{id}/mark_submitted`（pending -> submitted）
- FDA/EMA/PMDA：`category=fda_policy|ema_policy|pmda_policy`
  - 统计：`GET /v1/articles/stats/policies`（各类 total_count/year_count/positive_count）

## AI 对话

- 接口：`POST /v1/ai/chat`
- 统一包装：`{ code, message, data: { conversation_id, reply, tool_calls } }`
- 支持多轮：复用 conversation_id；messages 传当轮对话。
- 工具：财务数据查询/对比/图表/可用类型（基于本地 finance_records）。
- Persona：`persona=finance`（优先财务工具）或 `persona=general`（工具自动判定）。

