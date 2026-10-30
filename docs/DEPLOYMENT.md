# 部署与运维

> 面向 AI 助手的逐步部署指令见根目录 [DEPLOY.md](../DEPLOY.md)。本文是部署架构、端口、健康检查与生产化建议。

## 1. 组件与端口

| 组件 | 端口 | 启动 |
| --- | --- | --- |
| 应用（FastAPI） | 8000 | `make dev` |
| 物流 MCP Server | 8101 | `make mcp-up` / `make dev` |
| 售后 MCP Server | 8102 | `make mcp-up` / `make dev` |
| 主题分类器 | 8110 | `make classifier-up` |
| Langfuse | 3000 | `make langfuse-up` |
| MySQL | 3306 | `docker compose up -d` |
| Milvus | 19530 / 9091 | `docker compose up -d` |
| MinIO（Milvus 依赖） | 9000 / 9001 | 随 Milvus |

## 2. 本机开发

```bash
cp .env.example .env        # 填三组密钥
uv sync
docker compose up -d        # MySQL + etcd + MinIO + Milvus
make milvus-up              # 等 Milvus 健康
make seed && make seed-conv
make kb-build && make kb-vectorize
make dev                    # 起 MCP + 应用
```

验收：

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/
printf '{"user_id":"u1","message":"订单 1001 的物流到哪了"}' > /tmp/q.json
curl -s --max-time 90 http://localhost:8000/api/agent -H 'Content-Type: application/json' --data-binary @/tmp/q.json
```

## 3. 依赖服务

### MySQL

- 镜像 `mysql:8`，root/root（仅本地演示）；
- `sql/` 挂到 `/docker-entrypoint-initdb.d`，首启按文件名顺序执行 ch02–ch10 DDL；
- 表结构权威源是 `sql/`，ORM 只映射不 `create_all`。

### Milvus Standalone

- 必须 Standalone（Lite 不支持原生 BM25 全文检索）；
- 三件套：etcd + MinIO + Milvus；
- 集合 `knowledge`：`dense`(1024) + `text`(chinese analyzer) + `sparse`(BM25) + 标量字段。

### Langfuse（可选）

```bash
make langfuse-up     # 独立 compose，http://localhost:3000
```

首次约 2–3 分钟就绪，key 已 headless 预置；把三变量写进 `.env` 才挂回调。

### MCP Server

```bash
make mcp-up          # :8101 物流 / :8102 售后
make mcp-down
```

应用侧通过 `MCP_LOGISTICS_URL` / `MCP_AFTERSALES_URL` 动态发现工具。

## 4. 健康检查

| 服务 | 检查 |
| --- | --- |
| 应用 | `GET /` 200（页面）；业务接口需 DB/Milvus |
| MySQL | `docker compose exec -T mysql mysqladmin ping -proot --silent` |
| Milvus | `curl -sf http://127.0.0.1:9091/healthz` |
| 分类器 | `curl -sf http://127.0.0.1:8110/healthz` |
| Langfuse | `curl -sf http://localhost:3000` |

## 5. 生产化建议

当前仓库是**单机演示版**。上生产前至少补：

1. **鉴权与租户**：登录、租户隔离、RBAC；目前仅按 `user_id` 归属。
2. **反向代理与 TLS**：Nginx/Caddy，SSE 需关闭缓冲（`proxy_buffering off`）。
3. **密钥管理**：Vault/KMS/云 Secret，禁止明文 `.env` 上车。
4. **数据库**：MySQL 主从/备份、连接池、慢查询；Milvus 集群化。
5. **限流与熔断**：按用户/租户/IP；上游 429/5xx 退避。
6. **多副本**：checkpointer 换 Postgres/Redis 等共享存储（当前 AsyncSqliteSaver 单机）。
7. **观测告警**：Langfuse + Prometheus/Alertmanager；成本与错误率阈值。
8. **数据保留**：会话/审计/问题池的保留期与删除任务。

## 6. 常见问题

| 现象 | 处理 |
| --- | --- |
| MinIO/镜像拉不下 | 用镜像站拉后 `docker tag` 回原名；或改用 `milvusdb/minio`（本仓库已用） |
| 3306 被占 | 改端口或停旧容器（别擅自动用户数据） |
| `Field required` | `.env` 缺五项必填密钥 |
| 首次调模型 `Model does not exist` | `CHAT_MODEL` 不是上游真名 |
| Milvus 预热失败但应用起来 | 正常降级；检索接口需 Milvus |
| SSE 不流式 | 反代开了缓冲，关闭 `proxy_buffering` |
| 上下文预算不足 | 调 `CONTEXT_WINDOW_*` / `SUMMARY_*` |

## 7. 停机

```bash
make dev-down        # 关 MCP + 应用
make milvus-down     # 停 Milvus 三件套
make langfuse-down   # 停观测栈
docker compose down  # 停 MySQL 等（数据卷保留）
```
