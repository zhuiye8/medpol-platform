# 公开 API 文档（对外服务）

> 提供给前沿动态、国内政策与动态、项目申报、FDA/EMA/PMDA 政策以及 AI 对话页面使用。默认基础域名 `http://101.132.130.146`。
所有接口统一返回：
>
> ```json
> { "code": 0, "msg": "success", "data": { ... } }
> ```

## 文章分类枚举（ArticleCategory）

| 枚举值 | 中文说明 |
| --- | --- |
| `frontier` | 前沿动态 |
| `domestic_policy` | 国内政策与动态（国家医保局） |
| `project_apply` | 项目申报 |
| `fda_policy` | FDA 政策 |
| `ema_policy` | EMA 政策 |
| `pmda_policy` | PMDA 政策 |

## 通用字段

- `content_html`：原始 HTML 内容。
- `translated_content` / `translated_content_html`：若原文非中文，会生成对应的中文纯文本与 HTML（专业名词保持原文）。
- `summary`：AI 摘要（中文）。
- `ai_analysis`：AI 结构化分析（要点、风险、建议等）。
- `ai_results`：AI 任务调用记录，可按 `task_type`（`summary`/`translation`/`analysis`）区分。
- 分页参数：`page`（起始 1）、`page_size`（1-100）。
- 时间字段：ISO8601（UTC）。

## 1. 前沿动态

- 列表：`GET /v1/articles/?category=frontier&page=1&page_size=20`
- 详情：`GET /v1/articles/{article_id}`

## 2. 国内政策与动态（国家医保局）

- 列表：`GET /v1/articles/?category=domestic_policy&page=1&page_size=20`
- 详情：`GET /v1/articles/{article_id}`
- 数据源：https://www.nhsa.gov.cn/col/col147/index.html ，正文抓取 `div#zoom`。

## 3. 项目申报

- 列表：`GET /v1/articles/?category=project_apply&page=1&page_size=20`
- 详情：`GET /v1/articles/{article_id}`（如无需 AI 字段，可在客户端忽略 `translated_content`、`ai_analysis`）

## 4. FDA / EMA / PMDA 政策

- 列表：按分类调用 `GET /v1/articles/?category=fda_policy|ema_policy|pmda_policy`
- 详情：`GET /v1/articles/{article_id}`
- 统计：当前可使用列表响应的 `total` 字段；若需专门统计接口，可在后续版本扩展 `/v1/articles/stats?category=fda_policy`。

## 5. AI 对话接口（财务数据分析助手）

**状态**：✅ 已上线（v2.0 - 本地数据库架构）

**基础URL**: `http://101.132.130.146`

**数据来源**: 本地PostgreSQL数据库（每月1号凌晨4点自动同步）

**数据范围**: 2023年11月 至 2025年9月（持续更新中）

### 5.1 对话接口
**响应格式（统一包装）**:
```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "conversation_id": "会话ID",
    "reply": {
      "role": "assistant",
      "content": "集团最近几个月的营业收入呈现稳定增长态势..."
    },
    "tool_calls": [
      {
        "tool": "query_finance_data",
        "arguments": {
          "finance_type": "01",
          "keep_date": "2024-09",
          "company_numbers": ["001"]
        },
        "result": {
          "records": [
            {
              "company_number": "001",
              "finance_type": "01",
              "keep_date": "2024-09",
              "amount": 1234567.89,
              "unit": "CNY"
            }
          ]
        }
      }
    ]
  }
}
```

| 基因(合) | 二级 | 子公司 |
| 产业(合) | 二级 | 子公司 |
| 普林斯(合) | 二级 | 子公司 |
| 圣氏化学 | 二级 | 子公司 |
| 颐和堂 | 二级 | 子公司 |
| 华天宝 | 二级 | 子公司 |
| 国药控股 | 二级 | 子公司 |
| 医疗器械 | 二级 | 子公司（2025年新增） |
| 萨恩公司 | 二级 | 子公司（2025年新增） |

### 5.5 使用示例

#### JavaScript/TypeScript
```javascript
// 示例1：趋势分析
const response = await fetch('http://101.132.130.146/v1/ai/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    messages: [
      { role: 'user', content: '集团最近半年的营业收入趋势如何？' }
    ]
  })
});

const data = await response.json();
console.log(data.data.reply.content);  // AI分析结果
console.log(data.data.tool_calls);        // 调用的工具和数据

// 示例2：多轮对话
const conv_id = data.data.conversation_id;
const response2 = await fetch('http://101.132.130.146/v1/ai/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    conversation_id: conv_id,
    messages: [
      { role: 'user', content: '集团最近半年的营业收入趋势如何？' },
      { role: 'assistant', content: data.data.reply.content },
      { role: 'user', content: '那股份公司呢？' }  // 继续追问
    ]
  })
});
```

#### Python
```python
import requests

# 基础查询
response = requests.post(
    'http://101.132.130.146/v1/ai/chat',
    json={
        'messages': [
            {'role': 'user', 'content': '集团2024年3月的营业收入是多少？'}
        ]
    }
)

data = response.json()
print(data['data']['reply']['content'])
# 输出：2024年3月，集团(合)的营业收入为5.44亿元，同比增长5.28%。

# 公司排名查询
response = requests.post(
    'http://101.132.130.146/v1/ai/chat',
    json={
        'messages': [
            {'role': 'user', 'content': '2024年3月营业收入排名前5的公司'}
        ]
    }
)
```

#### cURL
```bash
# 对比分析
curl -X POST http://101.132.130.146/v1/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "对比集团和股份公司2024年Q1的营收"}
    ]
  }'

# 趋势分析
curl -X POST http://101.132.130.146/v1/ai/chat \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "分析联博公司最近3个月的利润趋势"}
    ]
  }'
```

### 5.6 多轮对话

AI助手支持上下文记忆，可以进行连续对话：

```json
{
  "conversation_id": "上一次返回的ID",
  "messages": [
    {"role": "user", "content": "集团最近的营收如何？"},
    {"role": "assistant", "content": "集团(合)最近6个月平均营收5.23亿元..."},
    {"role": "user", "content": "那利润呢？"},  // AI会理解这里的"集团"
    {"role": "assistant", "content": "集团(合)最近6个月平均利润..."},
    {"role": "user", "content": "对比一下股份公司"}  // AI会理解对比"利润"
  ]
}
```

### 5.7 工具函数能力（当前已启用）

AI 助手当前暴露 4 个财务数据工具，均基于本地 finance_records 数据表：

| 工具名称 | 功能 | 参数 | 使用场景 |
|---------|------|------|---------|
| `query_finance_data` | 查询指定财务类型 + 记账月份的数据 | `finance_type`、`keep_date`、`company_numbers`(可选) | 基础数据查询 |
| `compare_finance_data` | 按年/按月/按公司对比聚合 | `compare_dimension`、`finance_type`、`company_numbers`、`years`、`months` | 同比/环比/多公司对比 |
| `get_finance_chart_data` | 获取适合图表展示的聚合数据 | `finance_type`、`keep_date`、`chart_type`(可选) | 前端图表渲染 |
| `get_available_finance_types` | 列出当前可用的财务类型编号及名称 | 无 | 查询可用指标 |

**调用流程**
1. 用户提问 → 能力判定（需要财务/知识库/对话）
2. 如需要财务工具：模型自动触发 Function Calling → PostgreSQL 查询
3. AI 基于工具结果生成最终中文回答
### 5.8 性能与特性

- **响应时间**: 通常1.5-2秒（AI推理1.4秒 + 数据库查询<100ms）
- **数据更新**: 每月1号凌晨4点自动同步最新数据
- **数据规模**: 当前1016条记录，覆盖22个月
- **查询性能**: 基于PostgreSQL索引，支持复杂聚合查询
- **并发能力**: 支持高并发（仅受限于数据库连接池）
- **CORS**: 已配置，支持跨域访问
- **错误处理**: HTTP 500表示服务错误，请检查请求格式和参数

### 5.9 注意事项

- ✅ **数据时效性**: 每月初自动更新，查询前可先询问"最新数据是哪个月？"
- ✅ **金额单位**: 返回值单位为万元，AI会自动转换为易读格式（亿元）
- ✅ **公司名称**: 支持模糊匹配，如"集团"→"集团(合)"
- ✅ **时间推断**: 支持自然语言，如"上个月"、"今年Q1"
- ⚠️ **数据缺失**: 05号指标（所得税）暂无数据
- ⚠️ **历史数据**: 2023年11月之前的数据不可查询

## CORS 与安全

- 默认 `allow_origins=["*"]`.

