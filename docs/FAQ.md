# 常见问题

## 为什么不用一个 Agent 把整条链路都做了？

客服里有几处硬约束不能赌模型自觉：知识类不检索就答会编、退款不查政策就承诺、投诉硬接会火上浇油，这些一次出错就是事故。所以架构是混合的：**业务铁律写死在 LangGraph 图上（确定性 Workflow），模型只在真正需要开放推理的 ReAct 环里发挥**。

## 为什么 MySQL 和 Milvus 要双写，不只用 Milvus？

MySQL 存全字段原文（含章节路径、前后块指针、双写状态），是**权威源**，负责重建、重向量化、去重和审计；Milvus 是**派生的检索读模型**，只放服务在线检索够用的 `{id, dense, text, question, answer, section_path, category}`。双写按 `id` 对齐，`vectorize_status` 驱动幂等重跑。

## 为什么置信度闸放在生成之前？

主力 Agent 的回答是逐 token 流式吐给用户的，等答完再判已经晚了，弱证据的幻觉答案已经流出去。所以闸卡在检索之后、进 Agent 之前，证据不够直接短路兜底并落问题池。

## 怎么换模型 / 换上游？

改 `.env` 三组变量即可，代码不动：

- 聊天：`CHAT_BASE_URL` + `CHAT_MODEL` + `CHAT_API_KEY`（OpenAI 协议）；
- 嵌入：`EMBED_MODEL`（如 `BAAI/bge-m3`，要写上游真名）；
- 重排：`RERANK_MODEL`（走 `/rerank`，非 OpenAI 协议）。

注意 `CHAT_MODEL` 必须写上游认的真名，写错会在第一次调用时回 `Model does not exist`。

## 怎么新增一个工具？

1. 在 `app/tools/builtin/` 新建模块，写 `@tool`；
2. `registry.register(spec_from_langchain_tool(...))`，声明权限/超时/重试/结果格式化；
3. 写工具加到 `registry.WRITE_TOOLS`；
4. 补 `tests/tools/`。

新工具启动即注册，主 Agent 无需改核心代码。

## 怎么新增知识文档？

1. 放 `data/kb/*.md`（标题层级清晰、表格用标准 Markdown）；
2. 在 `app/kb/sources.py` 登记 `content_type`；
3. `make kb-build && make kb-vectorize`，再 `make eval-retrieval` 看召回。

## 怎么校准置信度阈值？

先建好知识库，再跑 `make calibrate-confidence`，它会用 ch04 评估集找 Youden J 最优点并回填 `EVIDENCE_CONFIDENCE_THRESHOLD`。换知识库内容后应重跑。

## 为什么看不到 turn trace 日志？

`app.main` 给 `app` 记录器配了 handler，turn trace 会同时打到终端和 `log/app.log`。确认起服务用的 `make dev`，并在 `log/app.log` 里 grep `route=` / `trace=`。

## 订单 / 物流数据是真的吗？

不是。演示版在 `app/tools/business.py` 里按入参稳定生成 mock 数据（同一订单号结果可复现），不建表、不接真实电商/物流系统。生产接入要换成真实 API 并加归属校验。

## 端口被占怎么办？

3306（MySQL）、19530（Milvus）、8000（应用）等被占会启动失败。要么停掉占用进程/容器，要么改端口（`.env` 的 `DATABASE_URL` / `MILVUS_URI`，应用的 `--port`）。

## 为什么所有问题都回“抱歉，我不太确定您的意思”？

旧版本会把模型的 401/402/403 异常降级成“其他”意图，用户因此看到固定兜底话术。
新版本会直接显示真实原因：

- HTTP `402` / SiliconFlow `code=30001`：当前 API Key 所属账户余额不足；
- HTTP `401/403`：Key 无效、被删除或没有模型权限；
- 处理方式：给 `.env` 里同一账号的 `CHAT_API_KEY` 充值，或换成有额度账号的 Key，然后重启应用。

先用以下命令验证模型账户，不要把 Key 发到聊天或提交到仓库：

```bash
set -a; source .env; set +a
curl -sS -o /tmp/model.json -w '%{http_code}\n' "$CHAT_BASE_URL/chat/completions" \
  -H "Authorization: Bearer $CHAT_API_KEY" -H 'Content-Type: application/json' \
  -d "{\"model\":\"$CHAT_MODEL\",\"messages\":[{\"role\":\"user\",\"content\":\"OK\"}],\"max_tokens\":8}"
cat /tmp/model.json
```

## 测试为什么有跳过 / 失败？

DB / Milvus / MCP 测试需要对应服务。本地没起服务时会跳过或报连接错；CI 里全部启动，当前 468 个全绿。先 `docker compose up -d && make milvus-up` 再 `make test`。

## 能不能不装 Docker？

MySQL 可以用本机 MySQL（改 `DATABASE_URL`）；但 Milvus 的 BM25 混合检索必须 Standalone，目前依赖 Docker 起三件套。没有 Docker 时，纯逻辑测试和 Web 页面仍可跑，检索/对话相关功能不可用。

## ch10 训练怎么更快？

训练脚本自适应 MPS/CUDA/CPU。有 Apple Silicon 或 NVIDIA GPU 时自动用加速；`ml` 组依赖较大，首次安装较慢。

## 生产环境还缺什么？

鉴权/多租户、限流熔断、PII 脱敏、数据保留期、checkpointer 换共享存储、密钥托管、反向代理 TLS、审计防篡改。详见 [docs/COMPLIANCE.md](COMPLIANCE.md) 与 [docs/DEPLOYMENT.md](DEPLOYMENT.md)。
