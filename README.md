# MewHelp — 生产级电商 AI 智能客服

一个从零到上线、覆盖 AI 应用核心链路的生产级电商智能客服系统:接模型、装工具、建知识库、做混合检索、搭 Workflow + Agent 混合架构,全部用 Python + FastAPI + LangChain/LangGraph 落地。

[![CI](https://github.com/Zennanzhoudev-Pixel/mewhelp/actions/workflows/ci.yml/badge.svg)](https://github.com/Zennanzhoudev-Pixel/mewhelp/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/Python-3.12-3776AB)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![LangChain](https://img.shields.io/badge/LangChain-1.3-1C3C3C)
![LangGraph](https://img.shields.io/badge/LangGraph-orchestration-1C3C3C)
![Milvus](https://img.shields.io/badge/Milvus-Standalone-00A0EA)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1)
![License](https://img.shields.io/badge/License-MIT-green)

## 它能干什么

用户问商品参数,它答得上来;查订单、追物流,它真去数据库和工具里翻,还只翻这位用户自己的单子;退款售后,政策怎么写就怎么办,不拍脑袋乱承诺;碰上投诉,它不硬接,转人工或建工单交用户自己选。

一条消息进来走的旅程:

```
用户消息 → 指代消解 → 意图识别 → 按意图分流
  ├─ 知识类(商品咨询/退款退货)  → 强制 RAG 检索 → 置信度闸 → 主力 Agent
  ├─ 业务类(订单/物流/售后)      → 主力 Agent(ReAct 循环,自己调工具)
  ├─ 投诉                        → 安抚话术 + 转人工/建工单按钮(不自动执行)
  └─ 闲聊                        → 固定话术(零模型调用)
```

## 技术栈

| 层 | 技术 |
|---|---|
| 服务层 | FastAPI + SQLAlchemy 2.0 async + MySQL 8.0 |
| AI 编排 | LangChain 1.3 + LangGraph(确定性 Workflow + 主力 Agent) |
| 检索层 | Milvus Standalone(BM25 + dense 双路,hybrid_search RRF 融合)+ BGE-M3 嵌入 + bge-reranker-v2-m3 重排 |
| 前端 | 原生 HTML + CSS + JavaScript,SSE 流式渲染 |
| 工程 | uv、pytest(TDD)、GitHub Actions CI、.env 密钥管理 |

## 功能清单(按章)

- **Ch01 纯对话**:OpenAI 协议接入、Prompt 工程化、SSE 逐 token 流式、结构化售后提取、token 预算裁剪。
- **Ch02 Function Calling**:5 个 `@tool`(查订单/商品/物流/FAQ/建工单)、MySQL 四表、工具注册/超时/重试/错误回灌、单轮收敛编排。
- **Ch03 RAG 基础**:Markdown 结构感知切块、双写建库(MySQL 权威源 + Milvus 向量)、幂等可重跑、对话挖知识、录入后台页 `/kb`。
- **Ch04 RAG 进阶**:BM25 + dense 混合检索、RRF 融合、bge-reranker 精排、Query 理解、带引用 + 拒答 + 低置信问题池、四策略分桶评估 `/rag-eval`。
- **Ch05 Workflow + Agent**:LangGraph 骨架、七类意图四出口、ReAct 循环、会话持久化(checkpointer)、转人工/建工单按钮。

## 快速开始

### 前置

- Python 3.12、[uv](https://docs.astral.sh/uv/)、Docker(跑 MySQL 与 Milvus)

### 1. 安装依赖

```bash
uv sync --all-groups
```

### 2. 配置密钥

```bash
cp .env.example .env
```

编辑 `.env`,填入三组上游密钥:`CHAT_API_KEY`(聊天)、`EMBED_API_KEY`(嵌入 BGE-M3)、`RERANK_API_KEY`(重排 bge-reranker-v2-m3)。`.env` 已被 gitignore,不会进仓库。

### 3. 起基础设施

```bash
docker compose up -d          # MySQL(自动跑 sql/ 下的 DDL)+ Milvus Standalone 三件套
make milvus-up                # 等待 Milvus 就绪
make seed                     # 灌 ch02 FAQ 种子
make kb-build && make kb-vectorize   # 建知识库 + 向量化
```

### 4. 起应用

```bash
make dev                      # http://localhost:8000
```

- 聊天页:http://localhost:8000/
- 知识库录入页:http://localhost:8000/kb
- RAG 评估页:http://localhost:8000/rag-eval
- 后台总览:http://localhost:8000/admin

## 验收演示

```bash
make eval         # ch01 结构化提取标注样例
make eval-agent   # ch02 工具选中标注样例
make eval-retrieval   # ch03 语义召回
make eval-rag     # ch04 四策略分桶评估(检索/证据覆盖/生成)
make eval-ch05    # ch05 五验收端到端
```

## 测试

确定性代码走 TDD,纯 Prompt/模型行为走标注样例评估;单测不打真实模型(FakeModel/依赖注入)。需要 MySQL 与 Milvus 的测试在服务不可用时自动跳过,CI 里全量跑。

```bash
make test
```

## 目录结构

```
app/
  api/          # /api/chat /api/agent /api/extract /api/actions /api/kb /api/jobs /api/admin /api/rag-eval
  core/         # llm / prompts / memory / embeddings / retrieval / rerank / selfcheck / intent / query_understanding / jobs
  db/           # base / models(8 表映射)/ repository
  tools/        # business(5 工具)/ registry / infra
  kb/           # chunking / documents / dedup / mining / dualwrite / milvus_client / sources
  graph/        # LangGraph:state / routing / nodes / build / runtime
  schemas/      # 请求/响应模型
  static/       # 聊天页 + 后台页
scripts/        # 冒烟 / 建库 / 挖知识 / 向量化 / eval / demo
sql/            # ch02–ch04 DDL 与种子
data/kb/        # 知识库源文档(faq / policy / manual / spec)
tests/          # 单测 + 标注样例 + 评估集
dev-notes/      # 各章开发过程留痕
```

## Roadmap

第 6–12 章(指代消解正式版、会话上下文管理、MCP 工具生态、可观测与数据飞轮、模型微调、全链路复盘、简历面试)不在此仓库范围内,后续按同一套工程纪律继续生长。

## License

[MIT](LICENSE)

