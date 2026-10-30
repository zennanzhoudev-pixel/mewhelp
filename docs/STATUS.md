# 能力状态

> 「能跑到什么程度」的权威说明。状态以本仓库代码与 CI 为准。

## 1. 已验证

| 项目 | 证据 |
| --- | --- |
| 纯逻辑单测（chunking/去重/路由/停止条件/工具引擎/上下文/飞轮/taxonomy 等） | 本地可跑，无外部服务 |
| 全量测试（含 MySQL / Milvus / MCP 集成） | GitHub Actions：**443 passed** |
| Web 应用启动与页面 | `uvicorn app.main:app` 可起，`/` `/kb` `/admin` `/rag-eval` `/review` `/observability` `/topics` 均 200 |
| 知识库切块（真实 6 份文档） | 52 块（faq 15 / policy 15 / manual 8 / spec 14），表格复制表头、关键条款识别 |
| CI 基础设施 | MySQL 8 + Milvus Standalone + MCP Server 自动起 |

## 2. 需要外部条件才能验证

| 能力 | 前置 |
| --- | --- |
| 真实对话 / 流式回答 | `.env` 三组密钥 |
| 工具调用（订单/商品/物流/售后） | 聊天上游 +（物流/售后）MCP Server |
| 知识检索 / 引用 / 拒答 | Milvus + 嵌入/重排上游 + 已建库 |
| 会话 / 审计 / 飞轮 / 评估落库 | MySQL |
| Langfuse trace / 成本 | Langfuse 自部署 + 三变量 |
| ch10 训练 / ONNX / 归类 | `ml` 组依赖（torch/transformers/onnx），GPU/MPS 更佳 |

## 3. 已实现（代码层面）

- ch01 流式对话、Prompt 工程、结构化提取、token 裁剪
- ch02 Function Calling、5 个业务工具、单轮收敛编排（后演进为图）
- ch03 切块、嵌入、MySQL/Milvus 双写、幂等重跑、挖知识
- ch04 混合检索、RRF、重排、Query 理解/扩写、四策略评估
- ch05 LangGraph 骨架、ReAct、checkpointer
- ch06 九类意图、指代消解、退款子流程、interrupt/resume
- ch07 三层上下文、异步摘要、多会话侧栏
- ch08 工具注册/执行引擎、MCP、审计、工单确认流
- ch09 Langfuse、置信度校准、三入口问题池、待审、评估趋势
- ch10 17 类多标签分类器、语料/训练/评测/ONNX/旁路归类

## 4. 明确未实现

| 项 | 说明 |
| --- | --- |
| 登录 / 鉴权 / 多租户 | 仅 `user_id` 归属，无登录体系 |
| 限流 / 熔断 / 多副本 | 单机演示 |
| 自动保留期 / 删除任务 | 需接入方实现 |
| PII 统一脱敏 | 仅 ch10 语料清洗有脱敏步骤 |
| 意图小模型降级 | 仅配置种子，运行时统一大模型 |
| ch11 / ch12 | 复盘与面试，不产生代码 |
