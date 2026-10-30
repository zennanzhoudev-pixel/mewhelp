# 架构设计

> 面向维护者与面试复盘：一条用户消息如何变成一句回答，系统由哪些层组成，边界在哪。

## 1. 设计目标

MewHelp 追求的不是「一个大 Agent 包打天下」，而是：

1. **硬约束交给代码**：知识类必须先检索、退款必须先取单再查政策、投诉不进 Agent——这些是事故级约束，不能赌模型自觉。
2. **灵活性交给 Agent**：订单/物流/售后这类需要多步工具组合的开放任务，交给 ReAct 环临场决策。
3. **可解释、可追溯**：每个回答带引用编号；每次工具调用有审计；每条请求有 trace。
4. **可运营、可进化**：答不好的问题进飞轮，人工审核补库；检索策略有评估集对照。

## 2. 分层架构

| 层 | 技术 | 职责 |
| --- | --- | --- |
| 交互层 | 原生 HTML/CSS/JS + SSE | 聊天页、订单选择器、工单预览、知识库/待审/观测/主题后台 |
| 服务层 | FastAPI | HTTP 接口、SSE 流、参数校验、错误分层（404/422/502/503） |
| 编排层 | LangGraph `StateGraph` | 确定性 Workflow 骨架 + ReAct 环；会话状态与中断恢复 |
| 检索层 | Milvus + BGE-M3 + bge-reranker | dense + BM25 混合召回、RRF、精排、置信度 |
| 工具层 | 注册中心 + 执行引擎 + MCP | 统一校验/权限/超时/重试/格式化/审计 |
| 存储层 | MySQL | 会话、消息、知识、工单、审计、问题池、待审、评估、主题 |
| 支撑层 | Langfuse + 飞轮 + RoBERTa 分类器 | 全链路可观测、成本、数据闭环、主题归类 |

## 3. 一条消息的旅程

```
POST /api/chat (SSE)
  → runtime.stream_turn
    → 建/取会话(MySQL conversations) → 落 user 消息
    → graph.astream(stream_mode=["messages","updates"])
      START
        → resolve_reference   指代消解 + Query 改写
        → classify_intent     九类意图 + confidence(JSON)
        → route_by_intent     写死映射到五出口
           ├ knowledge      → retrieve_knowledge → confidence_check
           │                    ├ strong → main_agent
           │                    └ weak   → fallback_reply(落问题池)
           ├ refund_flow    → fetch_order → retrieve_policy → main_agent
           │                    (缺订单号:interrupt 弹订单选择器)
           ├ business       → main_agent(ReAct)
           ├ escalate       → complaint_reply(转人工/建工单按钮)
           └ fallback_script→ script_reply(闲聊/其他固定话术)
        → main_agent ⇄ agent_tools   (ReAct,步数封顶)
        → log(落 assistant 消息 + trace)
      END
    → SSE 帧:tool / delta / citations / interrupt / actions / done
```

## 4. 图与状态

### 4.1 节点

| 节点 | 类型 | 职责 |
| --- | --- | --- |
| `resolve_reference` | Workflow | 结合历史补全指代/改写问句；已完整则透传 |
| `classify_intent` | Workflow | 九类意图 + 置信度，强制 JSON |
| `route_by_intent` | 条件边 | 九类 → 五出口，写死在代码 |
| `retrieve_knowledge` | Workflow | Query 扩写 → 混合检索 → 重排 → 编号证据 |
| `confidence_check` | Workflow + 条件边 | 生成前证据置信度闸（机械分 + 自评） |
| `fetch_order` | Workflow | 退款子流程取订单；缺号 interrupt |
| `retrieve_policy` | Workflow | 政策强制检索（扩写多查 + 去重合并） |
| `main_agent` | Agent | ReAct 推理步，带工具 |
| `agent_tools` | Agent | 执行工具；`create_ticket` 拦截为确认卡 |
| `complaint_reply` | Workflow | 安抚 + 转人工/建工单可选项 |
| `script_reply` | Workflow | 闲聊/其他固定话术 |
| `fallback_reply` | Workflow | 兜底话术 + 问题落池 |
| `log` | Workflow | trace 留痕 + assistant 消息落库 |

### 4.2 九类意图 → 五出口

| 意图 | 出口 |
| --- | --- |
| 商品咨询 | knowledge（强制检索） |
| 退款退货 / 售后 | refund_flow（取单 → 查政策 → Agent 判） |
| 物流 / 订单 / 人工 | business（Agent 自调工具） |
| 投诉 | escalate（不进 Agent） |
| 闲聊 / 其他 | fallback_script（固定话术） |

### 4.3 会话状态（`ConversationState`）

`messages`（`add_messages` reducer）、`summary` / `summary_upto_msg_id`（ch07 摘要锚点）、`user_id` / `conversation_id`、`intent` / `intent_confidence` / `resolved_query`、`order_id` / `order_data`、`route`、`evidence` / `citations` / `evidence_strong` / `evidence_confidence` / `fallback_source` / `retrieved_snapshot`、`answer`、`steps` / `tokens_used`、`suggested_actions`、`trace`（`merge_dict` reducer，入口用 `None` 重置）。

持久化：`AsyncSqliteSaver`（`data/ch05_checkpoints.sqlite`），`thread_id = str(conversation_id)`；MySQL 存业务消息与审计，checkpointer 存图状态，两者职责分离。

## 5. 检索管线（RAG）

```
用户问题
 → Query 理解:指代补全 + 口语归一 + 同义词扩展
 → Query 扩写(退款/售后等核心场景):多条查询
 → dense Top-50(BGE-M3, COSINE) + BM25 Top-50(Milvus 原生全文, chinese analyzer)
 → RRF 融合(hybrid_search)
 → bge-reranker-v2-m3 精排 Top-10
 → 置信度:精排 Top1 / 有效证据数 / Top1-Top2 分差 加权
 → 证据足:首尾组装(最相关放首尾) + 编号引用
 → 证据弱:拒答 + 落低置信问题池
```

评估：`tests/data/eval_ch04.jsonl` 300 题五桶（A 政策 / B 型号 / C 口语 / D 库外拒答 / E 跨文档），跑四种策略（vector / bm25 / hybrid / hybrid_rerank），指标含 Recall@5、MRR、证据覆盖度、答案覆盖度、Faithfulness、拒答率。

## 6. 工具系统

```
注册中心(ToolSpec: name / description / JSON Schema / permission / source / timeout)
 ├─ 内置:启动扫描 app/tools/builtin/*（import 即注册）
 │    query_order / query_product / query_faq / create_ticket / submit_refund
 └─ MCP:MultiServerMCPClient 连 :8101 / :8102 动态发现
      query_logistics（物流）/ query_warranty、query_return_status（售后）
执行引擎(唯一通道):
 查工具 → JSON Schema 校验 → 权限门 → 超时执行 → 暂时性故障重试 → 分诊 → 格式化 → 审计
```

要点：

- 写工具清单（`WRITE_TOOLS={"create_ticket"}`）由我们侧维护，不信任 MCP Server 自述；
- `create_ticket` 不自动重试；执行前还要走 interrupt 确认；
- 审计落 `tool_audit_logs`，被校验/权限拒绝也落；审计失败不反拦执行；
- 结果只挑回答需要的字段、内部枚举翻人话。

## 7. 上下文管理（ch07）

三层结构：

1. **最近**：原文全留（`context_window_turns` 轮）。
2. **中间**：按规则截短（用户原话保留，客服答只留开头，工具结果换一行标识）。
3. **最远**：后台异步摘要（`conversations.summary` + 锚点）。

调模型上下文固定顺序：`system`（人设/红线/工具定义）→ 中间层 → 最近原文 → 当前用户话 → 摘要+检索证据。摘要不单独占 system（保前缀缓存）。

## 8. 数据飞轮（ch09）

```
三入口: 检索低置信 / 生成前自评不足 / 用户👎
   → low_confidence_questions(带召回快照)
   → 标准化问法 + 查重合并
   → review_queue(occurrence_count 累加)
   → 人工通过/驳回
   → 通过:写 knowledge_chunks → 向量化 → 下一轮可检索
```

评估流水线复用 ch04 评估集，每轮分数落 `eval_runs`，连成趋势。

## 9. 可观测（ch09）

Langfuse 自部署，LangGraph 编译时挂一次回调（零侵入）。可看每个节点的 prompt、工具调用、检索结果、token、耗时；按意图统计成本。

## 10. 主题分类器（ch10）

```
低置信问题池 → 清洗(脱敏/纠错) → 17 类权威术语表 → 80/10/10 分层
 → 数据增强(只训练集) → LLM 预标 + 人工抽审
 → RoBERTa-wwm-ext 全参微调 → 测试集 P/R/F1 + 混淆矩阵
 → ONNX 导出 → :8110 推理服务 → 旁路批量写 topic_classifications → 主题分布页
```

实时对话主链路不调用分类器。

## 11. 数据模型（12 张表）

| 表 | 作用 |
| --- | --- |
| `conversations` | 会话壳（user_id/status/summary 等） |
| `messages` | 消息流水（user/assistant/tool） |
| `faq` | ch02 关键词 FAQ（已退居原始录入） |
| `tickets` | 人工工单 / 退款申请 |
| `knowledge_chunks` | 知识权威源 + 双写状态 |
| `qa_extraction_staging` | 挖知识暂存（含审核三态） |
| `tool_audit_logs` | 工具调用审计 |
| `low_confidence_questions` | 低置信问题池 |
| `review_queue` | 飞轮待审队列 |
| `eval_runs` | 评估轮次与趋势 |
| `faith_cases` | 编造个案台账 |
| `topic_classifications` | 多标签主题归类 |

DDL 在 `sql/ch02-ddl.sql` … `sql/ch10-ddl.sql`，容器首启按文件名顺序执行。

## 12. 部署拓扑与端口

| 组件 | 端口 | 启动方式 |
| --- | --- | --- |
| 应用 | 8000 | `make dev` |
| 物流 MCP | 8101 | `make mcp-up` / `make dev` |
| 售后 MCP | 8102 | 同上 |
| 主题分类器 | 8110 | `make classifier-up` |
| Langfuse | 3000 | `make langfuse-up` |
| Milvus | 19530 / 9091 | `docker compose up -d` |
| MySQL | 3306 | `docker compose up -d` |

## 13. 边界与非目标

- 演示版无登录/鉴权、多租户、限流、多副本；
- 订单/物流/售后数据为 mock（入参稳定随机），不接真实电商/物流系统；
- 意图识别的小模型降级路只留配置种子，运行时统一用大模型；
- ch11（全链路复盘）与 ch12（简历面试）不产生新代码。
