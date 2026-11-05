# 生产加固清单(8 项)

上一份差距清单里的 8 项已在本仓库落地为「配置开关控制」的能力。下面逐项说明:开关、怎么开、以及哪些仍需要你本人操作。

## 1. 登录 / 多租户 / RBAC

- 代码:`app/core/security.py`(JWT+口令散列)、`app/core/auth_middleware.py`、`app/core/deps.py`、`app/api/auth.py`、`app/db/models.py` 的 `User`、`conversations.tenant_id`。
- 开:`AUTH_ENABLED=true` + 设置 `JWT_SECRET`(强随机)。
- 接口:`POST /api/auth/register`、`POST /api/auth/login`、`GET /api/auth/me`。
- 首管理员:把 `ADMIN_USER`/`ADMIN_PASSWORD` 配好,注册同名用户即得 `admin` 角色。
- 登录页:`/login` 提供二维码确认、手机号验证码、账号密码三种方式。二维码由本系统一次性票据实现;若要直接使用飞书/企微扫码,需在企业后台创建 OAuth 应用并新增 provider。
- 短信:本地 `SMS_PROVIDER=console`;生产配置 `webhook`、`SMS_WEBHOOK_URL` 和 token,并保持 `SMS_DEBUG_RETURN_CODE=false`。
- RBAC:知识库、RAG 评估、待审队列、观测、主题、分类器验收、后台作业和 `/api/admin/*` 统一要求 `admin`;`viewer` 调用返回 403,无 token 返回 401。
- 角色界面:`customer → /`、`agent → /agent`、`admin → /console`;账号菜单按角色展示入口,直接访问无权限页面会被前端送回各自首页,后端仍做最终校验。
- 账号管理:管理员在 `/admin/users` 创建成员、分配角色、启停账号和重置密码。
- 多租户与用户归属:中间件每次请求从数据库校验账号状态和当前角色;跨租户访问返回 404,顾客访问同租户其他顾客的会话/工单/反馈同样返回 404。
- 数据库升级:已有库执行一次 `mysql ... < sql/ch12-console.sql`;全新环境由 MySQL 初始化目录按文件名顺序执行。

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

