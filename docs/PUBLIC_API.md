# 公开 API 文档

> 基础域名：`http://101.132.130.146:8000`  
> 所有接口统一返回：`{ "code": 0, "msg": "success", "data": { ... } }`

## 分类与 status
| category | 说明 | status 取值 |
| --- | --- | --- |
| `frontier` | 前沿动态 | — |
| `bidding` | 医保招标 | `policy_updates`（政策与动态）/`national_tenders`（国家集采）/`provincial_tenders`（省级集采） |
| `laws` | 法律法规 | — |
| `institution` | 中心制度 | — |
| `cde_trend` | CDE 动态 | `operations`（工作动态）/`accepted_products`（受理品种信息） |
| `industry_trend` | 行业动态 | `operations`（工作动态）/`accepted_products`（受理品种信息） |
| `project_apply` | 项目申报 | `pending` / `submitted` |
| `fda_policy` | FDA 政策 | — |
| `ema_policy` | EMA 政策 | — |
| `pmda_policy` | PMDA 政策 | — |

通用字段：`content_html`、`translated_title`、`translated_content`/`translated_content_html`、`summary`、`ai_analysis`（`{ "content": "...", "is_positive_policy": true/false/null }`）、`ai_results`（task_type: summary/translation/title_translation/analysis）、`is_positive_policy`、`tags`。时间：ISO8601。

## 文章列表 / 详情
- 列表：`GET /v1/articles/?category={category}&page=1&page_size=20`
  - 字段：id/title/translated_title/summary/publish_time/source_name/category/status/tags/source_url/is_positive_policy
  - 筛选：`status`（见上表），`q` 模糊搜索标题/译文标题/正文；政策/制度类推荐使用 `q`
  - `stats`（部分分类）
    - FDA/EMA/PMDA：`{ total_count, year_count, positive_count }`
    - 项目申报：`{ pending_total, pending_year, submitted_total, submitted_year }`
- 详情：`GET /v1/articles/{article_id}`（包含译文、ai_analysis、status、is_positive_policy、ai_results）
- 健康检查：`GET /healthz`

## 分类补充
- 前沿动态：`category=frontier`
- 医保招标：`category=bidding`，按 `status` 区分政策与动态/国家集采/省级集采
- 法律法规：`category=laws`，支持 `q` 模糊查询
- 中心制度：`category=institution`，支持 `q`
- CDE 动态：`category=cde_trend`，`status=operations|accepted_products`
- 行业动态：`category=industry_trend`，同上
- 项目申报：`category=project_apply`
  - 统计：`GET /v1/articles/stats/project_apply`
  - 状态更新：`POST /v1/articles/project_apply/{id}/mark_submitted`（pending -> submitted）
- FDA/EMA/PMDA：`category=fda_policy|ema_policy|pmda_policy`
  - 统计：`GET /v1/articles/stats/policies`

## AI 对话
- 接口：`POST /v1/ai/chat`
- 统一包装：`{ code, msg, data: { conversation_id, reply, tool_calls } }`
- 支持传入已有 `conversation_id` 持续对话
- 内置工具：财报查询、对比/图表（基于 finance_records）
- Persona：`finance` 优先启用财报工具；`general` 通用问答
