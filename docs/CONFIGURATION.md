# 配置说明

配置统一由 `app/config.py` 的 `Settings`（pydantic-settings）从 `.env` 读取。字段名大写即环境变量名（如 `chat_model` ↔ `CHAT_MODEL`）。

## 1. 必填项（缺了启动即报错）

| 环境变量 | 说明 |
| --- | --- |
| `CHAT_MODEL` | 聊天模型上游真名（无别名） |
| `CHAT_BASE_URL` | OpenAI 协议地址，如 `https://api.siliconflow.cn/v1` |
| `CHAT_API_KEY` | 聊天密钥 |
| `EMBED_API_KEY` | 嵌入密钥（BGE-M3） |
| `RERANK_API_KEY` | 重排密钥（bge-reranker-v2-m3） |

> 故意不给默认值：模型名/地址/密钥跟着账号走，猜错会在第一次调上游时抛看不懂的 401，不如启动时直接报 `Field required`。

## 2. 上游与模型

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `EMBED_BASE_URL` | `https://api.siliconflow.cn/v1` | 嵌入地址 |
| `EMBED_MODEL` | `BAAI/bge-m3` | 必须带 `BAAI/` 前缀 |
| `RERANK_BASE_URL` | `https://api.siliconflow.cn/v1` | 重排地址（Jina/Cohere 形状） |
| `RERANK_MODEL` | `BAAI/bge-reranker-v2-m3` | 重排模型名 |
| `CHAT_THINKING` | 空 | `disabled` 关思考链（推荐） |
| `CHAT_REASONING_EFFORT` | 空 | `low/high/max` |
| `CHAT_REASONING_SPLIT` | 空 | MiniMax 专属，`true` 把思考放独立字段 |

## 3. 存储

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | `mysql+asyncmy://root:root@localhost:3306/mewhelp` | 业务库 |
| `TEST_DATABASE_URL` | `mysql+asyncmy://root:root@localhost:3306/mewhelp_ch02_test` | 测试库 |
| `MILVUS_URI` | `http://localhost:19530` | Milvus Standalone |
| `CHECKPOINTER_DB_PATH` | `data/ch05_checkpoints.sqlite` | LangGraph 状态持久化 |

## 4. 检索与编排

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `TOKEN_BUDGET` | `2000` | 历史 token 预算 |
| `RECALL_TOP_K` | `50` | dense/BM25 各召回数 |
| `RERANK_TOP_K` | `10` | 精排截断 |
| `RERANK_MIN_SCORE` | `0.3` | 重排分阈值（低于判证据弱） |
| `SUBQUERY_SPLIT` | `true` | 多意图按子句拆分检索 |
| `MAX_AGENT_STEPS` | `6` | ReAct 步数封顶 |
| `EVIDENCE_CONFIDENCE_THRESHOLD` | `0.26` | 正式置信度闸（评估集校准值） |

## 5. 意图与上下文

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `INTENT_MODEL` | 空 | 空 = 回落 `CHAT_MODEL` |
| `INTENT_SMALL_MODEL` | 空 | 降级路种子（未接运行时） |
| `INTENT_MODE` | `accuracy` | `accuracy` / `cost`（cost 未实现） |
| `INTENT_CONF_THRESHOLD` | `0.6` | 降级升级阈值（种子） |
| `SUMMARY_TRIGGER_MESSAGES` | `30` | 距上次摘要新增满多少条触发 |
| `CONTEXT_WINDOW_TURNS` | `8` | 摘要后保留原文轮数 |
| `CONTEXT_WINDOW_MAX_TOKENS` | `3000` | 滑窗 token 上限 |
| `SUMMARY_MODEL` | 空 | 空 = 回落 `CHAT_MODEL` |

## 6. 工具与 MCP

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `MCP_LOGISTICS_URL` | `http://127.0.0.1:8101/mcp` | 物流 MCP |
| `MCP_AFTERSALES_URL` | `http://127.0.0.1:8102/mcp` | 售后 MCP |
| `TOOL_DEFAULT_TIMEOUT` | `5.0` | 内置工具超时（秒） |
| `MCP_TOOL_TIMEOUT` | `10.0` | MCP 工具超时（秒） |
| `TOOL_MAX_RETRIES` | `2` | 只读工具暂时性故障重试次数 |
| `DEMO_TICKET_DELAY_SECONDS` | `0.0` | >0 时人为拖慢建工单，演示写超时 |

## 7. 可观测

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `LANGFUSE_PUBLIC_KEY` | 空 | 三者齐全才挂回调 |
| `LANGFUSE_SECRET_KEY` | 空 | 同上 |
| `LANGFUSE_BASE_URL` | 空 | 如 `http://localhost:3000` |

## 8. `.env.example` 参考

```bash
CHAT_BASE_URL=https://api.siliconflow.cn/v1
CHAT_MODEL=deepseek-ai/DeepSeek-V4-Flash
CHAT_API_KEY=sk-xxx
CHAT_THINKING=disabled

EMBED_API_KEY=sk-xxx
RERANK_API_KEY=sk-xxx
TOKEN_BUDGET=2000

DATABASE_URL=mysql+asyncmy://root:root@localhost:3306/mewhelp
TEST_DATABASE_URL=mysql+asyncmy://root:root@localhost:3306/mewhelp_ch02_test

MCP_LOGISTICS_URL=http://127.0.0.1:8101/mcp
MCP_AFTERSALES_URL=http://127.0.0.1:8102/mcp
DEMO_TICKET_DELAY_SECONDS=0

# LANGFUSE_PUBLIC_KEY=pk-lf-mewhelp-local
# LANGFUSE_SECRET_KEY=sk-lf-mewhelp-local
# LANGFUSE_BASE_URL=http://localhost:3000
```

## 9. 调参建议

- **回答太松/编造多**：降低 `RERANK_MIN_SCORE` 不适用——应调高；或调高 `EVIDENCE_CONFIDENCE_THRESHOLD`（先跑 `make calibrate-confidence` 重新校准）。
- **召回不足**：先看 `make eval-rag` 的 Recall@5 与桶分布，再调 `RECALL_TOP_K` / 扩写，别直接堆 Top-K。
- **成本高**：降 `RECALL_TOP_K`、`RERANK_TOP_K`、`MAX_AGENT_STEPS`，用 `make cost-report` 看意图维度。
- **上下文爆**：调 `CONTEXT_WINDOW_TURNS` / `CONTEXT_WINDOW_MAX_TOKENS` / `SUMMARY_TRIGGER_MESSAGES`。
- **思考链拖慢**：`CHAT_THINKING=disabled`（上游支持时）。
