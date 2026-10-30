# 测试与评估

## 1. 分层策略

| 类型 | 对象 | 方式 |
| --- | --- | --- |
| TDD 单测 | 确定性代码：切块、去重、检索编排、路由、停止条件、工具引擎、上下文、飞轮、taxonomy | pytest，先红后绿，不打真实模型 |
| 标注样例 | 纯 Prompt / 数据类：提取、意图、改写、挖知识、飞轮标准化、预标 | 样例集跑通过率 |
| 评估集 | 检索质量、生成质量 | ch04 300 题五桶，四策略对照 |
| 集成测试 | MySQL / Milvus / MCP Server | 真实服务，CI 全量跑 |
| 前端 | Vibe Coding | 浏览器手动验收（无单测） |

## 2. 规模

- 测试文件：78 个；
- CI 用例：**443 个全部通过**（GitHub Actions，含 MySQL 8 + Milvus Standalone + MCP Server）；
- 评估集：`tests/data/eval_ch04.jsonl` 300 题（A 政策 / B 型号 / C 口语 / D 库外拒答 / E 跨文档，各 60）；
- 飞轮样例：`tests/data/flywheel_samples.json` 35 条；
- 其它样例：`extract_samples.json`、`intent`、`corp`、`mining_samples.json`、`query_rewrite_samples.jsonl`、`retrieval_samples.json`。

## 3. 目录

```
tests/
  core/     confidence / flywheel / llm_usage / observability / rerank / retrieval / selfcheck / taxonomy
  db/       flywheel 表 / low_confidence / tool_audit / topic_repository
  graph/    build / routing / state / runtime / nodes / ch06 / ch08 确认 / ch09 置信度
  kb/       milvus_hybrid / mining_review_gate
  tools/    engine / mcp_client / mcp_servers / registry / order_ownership / query_faq_rag
  test_*.py API、上下文、会话、配置、切块、抽取、评估、主题等
  data/     评估集与标注样例
```

## 4. 怎么跑

```bash
# 前置：MySQL + Milvus 已起（docker compose up -d && make milvus-up）
make test

# 单类
uv run pytest tests/core -q
uv run pytest tests/graph -q

# 评估与冒烟（需上游/知识库）
make eval-check && make eval-rag
make smoke-interrupt
make eval-ch05 / eval-ch06 / eval-ch07 / eval-ch08
make flywheel-samples && make eval-flywheel
make ch10-golden && make ch10-eval
```

> 无外部服务时，纯逻辑测试仍可跑；DB/Milvus/MCP 测试需要对应服务。CI 里全部启动，所以是 443 全绿。

## 5. CI

`.github/workflows/ci.yml`：

1. `uv sync`（锁定依赖）；
2. `docker compose up -d mysql etcd minio milvus-standalone`；
3. 等 MySQL / Milvus 健康；
4. `uv run pytest -q -rs`。

## 6. 评估指标

- 检索：Recall@5、MRR（按桶）；
- 证据：`expect_points` 机械覆盖度；
- 生成：答案覆盖度、Faithfulness、库外拒答率；
- 编造台账：跨轮累计、处置状态、证据快照；
- 裁判：temperature=0，`make judge-check` 对照人工处置。
