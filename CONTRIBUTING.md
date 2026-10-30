# 贡献指南

## 环境

- Python 3.12、uv、Docker（MySQL + Milvus）
- 复制 `.env.example` 为 `.env` 并填三组密钥

```bash
uv sync
docker compose up -d
make milvus-up
make seed
```

## 开发流程

1. **先写失败测试**（确定性代码走 TDD）；纯 Prompt/数据任务用标注样例或评估集验证。
2. 实现，跑 `make test`；涉及检索/生成再跑对应 `make eval-*`。
3. 提交前确认 `git status` 干净、没有 `.env`/密钥/数据库文件入仓。

## 提交规范

使用 Conventional Commits：

```
feat(ch08): 新增 MCP 工具动态发现
fix(graph): 修复退款子流程中断续跑
test(ch04): 补充 cross-doc 评估样例
docs: 完善架构与接口文档
```

## 扩展点

### 新增一个内置工具

1. 在 `app/tools/builtin/` 新建模块，写 `@tool`；
2. 调用 `registry.register(spec_from_langchain_tool(...))`；
3. 写权限（写工具加入 `WRITE_TOOLS`）、超时/重试、结果格式化；
4. 补测试（`tests/tools/`）。

### 新增一个图节点

1. 在 `app/graph/nodes.py` 实现（返回 state delta）；
2. 在 `app/graph/build.py` 注册节点与边；
3. 在 `app/graph/routing.py` 加条件边（如需要）；
4. 补 `tests/graph/`。

### 新增知识文档

1. 放到 `data/kb/*.md`（标题层级清晰，表格用标准 Markdown）；
2. 在 `app/kb/sources.py` 登记 `content_type`；
3. `make kb-build && make kb-vectorize`，再跑 `make eval-retrieval`。

## 代码规范

- 中文注释说明「为什么」，代码表达「做什么」；
- 配置进 `Settings`，不写死；
- 错误分层：参数 422、会话 404、数据库 503、上游 502；
- 流式接口保持 SSE 帧契约（见 `docs/API.md`）；
- 不要提交 `.env`、`data/*.db*`、`data/ch10/*`（报告除外）、日志。

## PR 检查清单

- [ ] `make test` 通过（或说明为何需要外部服务）
- [ ] 涉及接口的改动已更新 `docs/API.md`
- [ ] 涉及配置的改动已更新 `docs/CONFIGURATION.md` 与 `.env.example`
- [ ] 没有密钥/个人数据/大文件
- [ ] 变更说明写清「为什么」与「影响面」
