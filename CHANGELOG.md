# 变更记录

## [0.1.0] - 2026-10-29

首个完整版本（ch01–ch10），对齐课程最终源码。

### 新增

- ch01 流式对话、Prompt 工程、结构化售后提取、token 裁剪
- ch02 Function Calling、5 个业务工具、MySQL 四表
- ch03 结构感知切块、BGE-M3 嵌入、MySQL/Milvus 双写、对话挖知识
- ch04 BM25 + dense 混合检索、RRF、bge-reranker、Query 理解/扩写、300 题四策略评估
- ch05 LangGraph Workflow + Agent ReAct、checkpointer
- ch06 九类意图、指代消解、退款子流程、interrupt/resume 订单选择器
- ch07 三层上下文、异步摘要、前缀缓存、多会话侧栏
- ch08 工具注册中心、统一执行引擎、MCP 接入、工单确认流、审计
- ch09 Langfuse 可观测、置信度校准、数据飞轮、待审队列、评估趋势
- ch10 RoBERTa-wwm-ext 多标签主题分类器（语料/训练/评测/ONNX/旁路归类）

### 工程

- uv 锁定依赖、GitHub Actions CI（MySQL + Milvus + MCP）
- 全量 443 个测试通过
- 架构/设计/接口/配置/测试/部署/合规/状态文档
