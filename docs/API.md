# 接口与核心函数

基础地址：`http://localhost:8000`。除 SSE 外均为 JSON。

## 1. 聊天主入口（SSE）

### `POST /api/chat`

请求：

```json
{"user_id": "u1", "message": "订单 1001 的物流到哪了", "conversation_id": null}
```

- `conversation_id` 为空则新建，由 `done` 帧回传。

响应：`text/event-stream`，帧格式如下（`data: <json>`，空行分隔）：

| 帧 | 示例 | 含义 |
| --- | --- | --- |
| tool | `{"event":"tool","name":"query_order"}` | 本轮调用了某工具 |
| delta | `{"delta":"您的订单"}` | 回答 token 片段 |
| citations | `{"event":"citations","items":[...]}` | 知识引用（编号/章节/原文） |
| interrupt | `{"event":"interrupt","kind":"select_order","orders":[...]}` | 中断：选订单 / 确认工单 |
| actions | `{"event":"actions","items":[...]}` | 可选项（转人工/建工单） |
| done | `{"event":"done","conversation_id":12}` | 结束 |
| error | `event: error` + `{"message":"..."}` | 错误（流已 200，只能走帧） |
| 终止 | `data: [DONE]` | 流终止哨兵 |

## 2. 非流式 Agent

### `POST /api/agent`

请求：

```json
{"user_id":"u1","message":"订单 1001 的物流到哪了","conversation_id":null}
```

响应 `AgentResponse`：

```json
{
  "conversation_id": 12,
  "answer": "您的订单 1001 已发货…",
  "tool_calls": [{"id":"c1","name":"query_order","args":{"order_id":"1001"}}],
  "tool_results": [{"tool_call_id":"c1","name":"query_order","ok":true,"content":"{...}"}],
  "suggested_actions": [],
  "interrupt": null
}
```

- `interrupt` 非空时表示流程停在缺槽位/待确认：`select_order`（带订单列表）或 `confirm_ticket`（带工单预览）。
- 错误：404 会话不存在、422 参数校验、502 上游、503 数据库。

## 3. 结构化提取

### `POST /api/extract`

请求：`{"text":"订单 MH20260701123 散架了,我要退款"}`

响应：

```json
{"order_id":"MH20260701123","request_type":"退款","expected_solution":"到货损坏要求退款"}
```

`request_type` ∈ 退款 / 换货 / 维修 / 投诉 / 其他；订单号缺失为 `null`。

## 4. 动作（按钮触发）

### `POST /api/actions/create-ticket`

```json
{"conversation_id":5,"description":"屏幕碎了","ticket_type":"售后"}
```

响应：`{"ticket_no":"T2026...","status":"已转人工"}`。

### `POST /api/actions/create-refund`

```json
{"conversation_id":5,"order_id":"1001","reason":"七天无理由"}
```

`reason` ∈ 七天无理由 / 质量问题 / 发错货 / 不想要了 / 其他。

响应：`{"ticket_no":"T2026...","status":"退款申请已提交"}`。

### `POST /api/actions/resume`

```json
{"conversation_id":5,"order_id":"1001"}
```

或工单确认：

```json
{"conversation_id":5,"confirmed":true}
```

## 5. 会话与反馈

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/conversations?user_id=u1` | 会话侧栏（新在前、首问预览、是否已摘要） |
| GET | `/api/conversations/{id}/messages` | 回载历史原文 |
| POST | `/api/feedback` | `{conversation_id,rating:"up"/"down",question}`；👎 入问题池 |

## 6. 知识库（`/api/kb`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/kb/overview` | 库存/待向量化/Milvus 条数/双写一致性/暂存 |
| POST | `/api/kb/preview` | 切块预览（dry-run，不写库） |
| POST | `/api/kb/ingest` | 录入（可顺手向量化；按指纹幂等） |
| POST | `/api/kb/vectorize` | 补 pending |
| POST | `/api/kb/search` | 检索自测（vector/bm25/hybrid/hybrid_rerank） |
| GET | `/api/kb/staging` | 挖知识暂存三态 |
| POST | `/api/kb/staging/approve` | 暂存通过 |
| POST | `/api/kb/staging/reject` | 暂存驳回 |

## 7. 飞轮待审（`/api/review`）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/review/queue` | 待审队列（分页/状态） |
| GET | `/api/review/{id}` | 详情（用户原话 + 召回快照） |
| POST | `/api/review/{id}/approve` | 通过并写回知识库（`{"approved_answer":"..."}`） |
| POST | `/api/review/{id}/reject` | 驳回 |

## 8. 主题与评估

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/topics/distribution` | 17 类主题分布 |
| GET | `/api/topics/questions?label=` | 某类问题列表 |
| GET | `/api/rag-eval/overview` | 四策略报告（只读产物） |
| GET | `/api/rag-eval/faith-cases` | 编造个案台账（分页/状态） |
| POST | `/api/rag-eval/faith-cases/{id}/status` | 处置状态（需说明） |

## 9. 观测 / 后台 / 作业 / 验收

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/observability/overview` | 成本/质量/趋势 |
| GET | `/api/admin/overview` | 后台聚合卡片 |
| GET | `/api/jobs` | 作业清单 |
| POST | `/api/jobs/{name}` | 发起白名单作业 |
| GET | `/api/jobs/{name}` | 状态 + 日志尾 |
| POST | `/api/jobs/{name}/stop` | 停止 |
| GET | `/api/acceptance/overview` | 分类器验收总览 |
| GET | `/api/acceptance/eval` | 评估报告 |
| GET | `/api/acceptance/data` | 数据视图 |
| GET | `/api/acceptance/errors` | 判错样本 |
| GET | `/api/acceptance/service` | 分类器服务状态 |
| POST | `/api/acceptance/classify` | 单条归类 |

## 10. 核心函数索引

### 编排（`app/graph/`）

- `build._builder()` / `build_graph(checkpointer)`：组装/编译图
- `runtime.init_graph()` / `close_graph()` / `run_turn` / `resume_turn` / `stream_turn` / `stream_resume`
- `routing.route_by_intent` / `confidence_gate` / `should_continue`
- `nodes.resolve_reference` / `classify_intent` / `retrieve_knowledge` / `confidence_check` / `fetch_order` / `retrieve_policy` / `main_agent` / `agent_tools` / `complaint_reply` / `script_reply` / `fallback_reply` / `log_node`

### 核心能力（`app/core/`）

- `llm.get_chat_model` / `structured` / `needs_non_streaming_tools`
- `embeddings.embed_texts` / `embed_query`
- `retrieval.search_knowledge` / `arrange_head_tail` / `split_clauses`
- `rerank.rerank`
- `query_understanding.understand` / `expand_queries`
- `coref.resolve`
- `intent.classify`
- `memory.trim_history` / `build_window` / `summary_line`
- `summarizer.run_summary` / `maybe_schedule_summary`
- `confidence.compute_evidence_confidence` / `snapshot_from_hits`
- `selfcheck.check_sufficient`
- `flywheel.normalize_and_match` / `process_pending`
- `observability.attach_observability` / `tag_intent`
- `taxonomy.terminology_table`
- `jobs.start` / `stop` / `status` / `tail`

### 工具（`app/tools/`）

- `registry.scan_builtin` / `register` / `all_specs` / `permission_for`
- `engine.execute_tool_call` / `validate_args`
- `mcp_client.load_mcp_tools`
- 内置：`query_order` / `query_product` / `query_faq` / `create_ticket` / `submit_refund`

### 知识库（`app/kb/`）

- `chunking.split_sections` / `recursive_split` / `apply_sentence_overlap` / `split_table_rows`
- `documents.build_chunks`
- `dedup.normalize_question` / `dedupe`
- `mining.mine` / `extract_qa`
- `dualwrite.write_pending` / `vectorize_pending`
- `milvus_client.get_client` / `ensure_collection` / `upsert_vectors` / `hybrid_search` / `bm25_search` / `dense_search`

### 数据层（`app/db/`）

`repository` 提供会话/消息/FAQ/工单/知识/暂存/审计/问题池/待审/评估/台账/主题的 CRUD 与统计。
