# 能力状态

> 「能跑到什么程度」的权威说明。状态以本仓库代码与 CI 为准。

## 1. 已验证

| 项目 | 证据 |
| --- | --- |
| 纯逻辑单测（chunking/去重/路由/停止条件/工具引擎/上下文/飞轮/taxonomy 等） | 本地可跑，无外部服务 |
| 全量测试（含 MySQL / Milvus / MCP 集成） | 本地：**467 passed**；GitHub Actions 随每次 push 复跑 |
| Web 应用启动与页面 | 顾客端、独立登录、客服工作台、管理控制台、账号与原有后台页面均可达 |
| 登录方式 | 用户名密码、手机号一次性验证码、二维码手机确认 |
| 多角色界面 | `customer → /`、`agent → /agent`、`admin → /console` |
| 人工客服 | 转人工、排队、认领、回复、顾客增量接收、释放与结束会话 |
| 后台权限 | `admin` 可访问全部管理 API；`viewer` 返回 403；无 token 返回 401 |
| 租户隔离 | 会话历史、续跑、工单、退款、反馈均带租户校验；跨租户返回 404 |
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
- ch11 生产加固：JWT/PBKDF2、RBAC、Redis 限流、熔断、Postgres checkpointer、
  语义历史、Skill、保留期、PII 脱敏、审计哈希链、TLS/监控/备份部署产物
- ch12 身份与协同：独立登录页、账号管理、四种兼容角色、真实人工客服工作台

## 4. 明确未实现

| 项 | 说明 |
| --- | --- |
| 用户长期画像 | 已有语义历史；画像字段与写回策略需业务定义 |
| 完整 Skill 协议 | 当前为按意图注入 `skills/*.md` 的轻量 Skill |
| 真实生产基础设施 | 公网域名、TLS 证书、Vault/KMS、MySQL/Milvus 集群与监控实例需部署方提供 |
| 合规口径 | 保留天数、隐私告知、DPA、等保材料需按企业/地区要求确认 |
