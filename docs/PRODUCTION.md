# 生产加固清单(8 项)

上一份差距清单里的 8 项已在本仓库落地为「配置开关控制」的能力。下面逐项说明:开关、怎么开、以及哪些仍需要你本人操作。

## 1. 登录 / 多租户 / RBAC

- 代码:`app/core/security.py`(JWT+口令散列)、`app/core/auth_middleware.py`、`app/core/deps.py`、`app/api/auth.py`、`app/db/models.py` 的 `User`、`conversations.tenant_id`。
- 开:`AUTH_ENABLED=true` + 设置 `JWT_SECRET`(强随机)。
- 接口:`POST /api/auth/register`、`POST /api/auth/login`、`GET /api/auth/me`。
- 首管理员:把 `ADMIN_USER`/`ADMIN_PASSWORD` 配好,注册同名用户即得 `admin` 角色。
- RBAC:知识库、RAG 评估、待审队列、观测、主题、分类器验收、后台作业和 `/api/admin/*` 统一要求 `admin`;`viewer` 调用返回 403,无 token 返回 401。
- 页面入口:聊天页右上角「后台管理」按角色显隐;直接打开后台页面时也会校验角色并跳回聊天页。真正的权限边界在后端 API。
- 多租户:中间件把 token 里的 `tenant` 写入 `request.state.tenant_id`;会话列表、历史、续跑、工单、退款和反馈均校验会话所属租户,跨租户统一返回 404。

## 2. 限流 / 熔断 / 多副本

- 限流:`app/core/ratelimit.py` + 中间件;开 `RATE_LIMIT_ENABLED=true`,按客户端 IP 滑动窗口计数。配置 `REDIS_URL` 后使用 Redis 共享计数,多副本不会各自计算。
- 熔断:`app/core/circuit.py`,已接入嵌入与重排调用;开 `CIRCUIT_BREAKER_ENABLED=true`(默认开)。
- 多副本:checkpointer 换 Postgres(见第 7 项)后,应用可水平扩展;`langfuse`/MySQL/Milvus 各自独立。需要你:部署编排(K8s/多实例 + 负载均衡)。

## 3. 意图小模型降级路

- 代码:`app/core/intent.py` 的 `classify`。
- 开:`INTENT_MODE=cost` + `INTENT_SMALL_MODEL=<小模型真名>`;小模型置信度低于 `INTENT_CONF_THRESHOLD` 时升级大模型重判。

## 4. 语义检索历史 / 长期记忆

- 语义检索历史:`app/core/memory.py` 的 `search_history` + `nodes._inject_semantic_history`;开 `SEMANTIC_HISTORY_ENABLED=true`。
- 长期记忆(用户画像):本仓库未做持久画像,语义历史已覆盖「跨轮补捞」;画像需你定义字段与写回策略后扩展 `conversations`/新表。

## 5. Skill 机制

- 代码:`app/core/skills.py`;开 `SKILLS_ENABLED=true`,技能包放 `skills/*.md`(示例已给退款/物流两个)。
- 说明:这是「按意图注入指令包」的简化 Skill,非 Anthropic 完整 SKILL.md 规范。

## 6. 数据保留期

- 代码:`app/core/retention.py` + `scripts/retention.py`;开 `RETENTION_DAYS_CONVERSATIONS/AUDIT/LOW_CONF`。
- 跑:`make retention` 或挂 cron。

## 7. checkpointer 多副本

- 代码:`app/graph/runtime.py` 支持 `CHECKPOINTER_BACKEND=postgres`。
- 依赖:`uv sync --group postgres`。
- 需要你:起一个 Postgres,把 `CHECKPOINTER_POSTGRES_URL` 配好;表由 `AsyncPostgresSaver.setup()` 自建。

## 8. TLS / 密钥托管 / 审计防篡改 / PII 脱敏

- TLS:`deploy/nginx.conf`(反代 + 证书);证书签发与域名归你。
- 密钥托管:本仓库只从环境变量读 key(便于 Vault/KMS/云 Secret 注入);真正的 Vault/KMS 接入是基础设施,由你选型注入。
- 审计防篡改:`tool_audit_logs` 增加 `prev_hash`/`hash` 哈希链(ch11-hardening.sql + repository)。
- PII 脱敏:`app/core/pii.py`,审计内容/参数入库前打码(手机号/邮箱/带前缀单号);开 `PII_MASK_ENABLED=true`(默认开)。

