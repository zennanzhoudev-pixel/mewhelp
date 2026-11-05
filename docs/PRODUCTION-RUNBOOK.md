# 生产上线 Runbook(你必须自己做的那 6 项)

> 这是「部署环境 + 合规决策」类操作,无法由 AI 替你在你的服务器上执行。每项给了可直接照抄的命令与验收方式。所有命令里的占位符(`mewhelp.example.com`、`<密码>`、`<IP>` 等)都要换成你的真实值。

## 1. 开启鉴权(JWT + 管理员)

### 1.1 生成密钥

```bash
openssl rand -hex 32
```

把输出的 64 位十六进制串复制下来,作为 `JWT_SECRET`。

### 1.2 写 `.env`

```bash
cd /Users/mac/Documents/Codex/2026-10-29/https-ycnipcoc81qb-feishu-cn-wiki-ed8gwv3x3iicppk1ewtcan5bn2d/mewhelp
```

编辑 `.env`,追加/取消注释:

```bash
AUTH_ENABLED=true
JWT_SECRET=<第 1.1 步生成的串>
ADMIN_USER=admin
ADMIN_PASSWORD=<你设的强密码,至少 12 位>
```

### 1.3 重启并注册首个管理员

```bash
make dev   # 或你现有的启动方式,重启让它读到新配置
```

注册(用户名与密码匹配 `ADMIN_USER`/`ADMIN_PASSWORD` 时才授予 admin):

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<强密码>","tenant_id":"default"}'
```

返回里 `role` 应为 `admin`,`token` 就是你的登录凭证。

### 1.4 打开登录页

浏览器访问 `http://localhost:8000/login`。支持扫码确认、手机号验证码和账号密码。
管理员登录后进入 `/console`；人工客服进入 `/agent`；顾客进入 `/`。

### 1.5 带 token 调用

```bash
TOKEN=<上一步返回的 token>
curl -X POST http://localhost:8000/api/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"u1","message":"订单 1001 的物流到哪了"}'
```

前端已统一处理登录跳转、Bearer token、角色菜单与账号状态。若使用手机扫码，`PUBLIC_BASE_URL`
必须是手机可访问的局域网地址或公网 HTTPS 域名。

## 2. TLS 证书 + 域名 + 反向代理

### 2.1 域名与 DNS

1. 买域名,在 DNS 服务商加一条 A 记录,把 `mewhelp.example.com` 指向你的服务器 IP。
2. 等解析生效:`dig +short mewhelp.example.com` 返回你的 IP。

### 2.2 安装 nginx + certbot(以 Ubuntu/Debian 为例)

```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

### 2.3 签发证书

```bash
sudo certbot --nginx -d mewhelp.example.com
```

### 2.4 合并反代配置(SSE 必须关缓冲)

仓库里的 `deploy/nginx.conf` 已经是完整示例,把 `server_name` 和证书路径改成你的之后:

```bash
sudo cp deploy/nginx.conf /etc/nginx/sites-available/mewhelp
sudo ln -s /etc/nginx/sites-available/mewhelp /etc/nginx/sites-enabled/mewhelp
sudo nginx -t && sudo systemctl reload nginx
```

验收:`curl -sI https://mewhelp.example.com/` 返回 200;SSE 是否流式可以用浏览器打开聊天页发一句看是否逐字出。

> 关键点:`proxy_buffering off` 不能删,否则回答不会逐字流式,会攒成一整段。

## 3. 多副本:Postgres checkpointer + Redis 限流 + 多实例

### 3.1 起 Postgres 与 Redis

```bash
docker run -d --name mewhelp-pg -p 5432:5432 \
  -e POSTGRES_USER=mewhelp -e POSTGRES_PASSWORD=<pg密码> -e POSTGRES_DB=mewhelp \
  postgres:16
docker run -d --name mewhelp-redis -p 6379:6379 redis:7
```

### 3.2 依赖 + 配置

```bash
uv sync --group postgres
```

`.env` 追加:

```bash
CHECKPOINTER_BACKEND=postgres
CHECKPOINTER_POSTGRES_URL=postgresql+psycopg://mewhelp:<pg密码>@127.0.0.1:5432/mewhelp
```

表由 `AsyncPostgresSaver.setup()` 在启动时自动建。

> 说明:限流当前是内存版(单实例够用)。多副本下每个实例各自计数会失效,需要把 `app/core/ratelimit.py` 换成 Redis 实现——这个改动我可以帮你做,做之前先按「多实例 + Postgres checkpointer」跑,限流暂时只在单实例生效。

### 3.3 多实例 + nginx 负载均衡

起两个应用进程:

```bash
make dev &            # 8000
PYTHONPATH=. uv run uvicorn app.main:app --host 127.0.0.1 --port 8001 &
```

nginx `upstream` 配置:

```nginx
upstream mewhelp_backend {
    server 127.0.0.1:8000;
    server 127.0.0.1:8001;
}
```

因为会话状态在 Postgres checkpointer、业务在 MySQL,两个实例共享状态,**无需 sticky session**;任一实例挂了另一台继续服务。

## 4. 密钥托管(Vault / KMS / 云 Secret)

代码只从环境变量读密钥(`app/config.py` 的 `Settings`),所以**只要环境变量来自 Secret,代码一行不用改**。三条路线任选:

### 4.1 云/K8s Secret(最省事)

```bash
kubectl create secret generic mewhelp-secrets \
  --from-literal=CHAT_API_KEY=... \
  --from-literal=EMBED_API_KEY=... \
  --from-literal=RERANK_API_KEY=... \
  --from-literal=JWT_SECRET=...
```

Deployment 里用 `envFrom: [{secretRef: {name: mewhelp-secrets}}]` 注入。

### 4.2 Docker(简单场景)

```bash
docker run -e CHAT_API_KEY=... -e EMBED_API_KEY=... -e RERANK_API_KEY=... ...
```

密钥来自部署平台,不在镜像、不在 git、不在 `.env` 里。

### 4.3 Vault(自建)

```bash
vault kv put secret/mewhelp CHAT_API_KEY=... EMBED_API_KEY=... RERANK_API_KEY=... JWT_SECRET=...
```

用 Vault Agent/Sidecar 把 `secret/mewhelp` 渲染成环境变量或文件注入应用。

> 底线:`.env` 已在 gitignore,但生产仍建议彻底移除本地 `.env`,改用上面的注入方式;并给日志/CI 做脱敏,避免 key 被打印。

## 5. 数据库/向量库备份 + 监控告警

### 5.1 MySQL 备份

```bash
# 全量备份
docker exec mewhelp-mysql sh -c 'exec mysqldump --all-databases -uroot -proot' > backup-$(date +%F).sql

# 定时(每日 03:00)
0 3 * * * docker exec mewhelp-mysql sh -c 'exec mysqldump --all-databases -uroot -proot' > /backup/mewhelp-$(date +\%F).sql
```

高可用:MySQL 主从(或云 RDS 自带备份)。

### 5.2 Milvus 备份

Milvus 2.6 用 `milvus-backup` 工具备份集合数据;或者对 etcd + MinIO + Milvus 三个数据卷做快照(停止写入时最稳)。

```bash
# 快照三个数据卷(单机快照路线)
docker run --rm -v mewhelp_mewhelp-milvus-data:/mnt/milvus -v /backup:/backup alpine tar czf /backup/milvus-$(date +%F).tgz -C /mnt/milvus .
docker run --rm -v mewhelp_mewhelp-milvus-etcd:/mnt/etcd -v /backup:/backup alpine tar czf /backup/etcd-$(date +%F).tgz -C /mnt/etcd .
docker run --rm -v mewhelp_mewhelp-milvus-minio:/mnt/minio -v /backup:/backup alpine tar czf /backup/minio-$(date +%F).tgz -C /mnt/minio .
```

### 5.3 监控 + 告警

组件:Prometheus + node_exporter(机器)+ mysqld_exporter(MySQL)+ milvus 自带指标(9091/metrics)+ Alertmanager。

```bash
docker run -d --name node-exporter -p 9100:9100 prom/node-exporter
docker run -d --name mysqld-exporter -p 9104:9104 \
  -e DATA_SOURCE_NAME="root:root@(127.0.0.1:3306)/" prom/mysqld-exporter
```

Prometheus 里加两个 job:

```yaml
scrape_configs:
  - job_name: node
    static_configs: [{targets: ["localhost:9100"]}]
  - job_name: mysql
    static_configs: [{targets: ["localhost:9104"]}]
  - job_name: milvus
    static_configs: [{targets: ["localhost:9091"]}]
```

应用层的错误率/延迟/token 成本用 Langfuse(已接)配合 Prometheus 自定义 exporter 或日志采集;告警规则按「错误率 > x%、P99 > y、token 成本 > 预算」设。

## 6. 数据保留期

1. 按合规口径定天数(例如:会话 90 天、审计 180 天、低置信池 180 天)。
2. `.env` 配置:

```bash
RETENTION_DAYS_CONVERSATIONS=90
RETENTION_DAYS_AUDIT=180
RETENTION_DAYS_LOW_CONF=180
```

3. 手动跑一次验证:

```bash
make retention
```

4. 挂 cron(每日 03:30):

```cron
30 3 * * * cd /path/to/mewhelp && /usr/local/bin/uv run python scripts/retention.py >> log/retention.log 2>&1
```

验收:日志输出 `已清理: {'messages': N, 'conversations': N, ...}`,且过期数据确实没了。

## 上线顺序建议

1 → 6 → 4(先本地跑通,再迁移密钥)→ 3 → 2 → 5。先保证单机功能与数据安全,再做多副本与对外暴露。

## 仓库里已备好的现成产物

| 文件 | 用途 |
| --- | --- |
| `Dockerfile` | 构建应用镜像(uv 装依赖,--no-sync 启动) |
| `docker-compose.prod.yml` | MySQL + Postgres + Redis + Milvus + 2 个应用副本 + nginx |
| `deploy/prod.env.example` | 生产 compose 的环境变量模板(服务名已对齐) |
| `deploy/nginx.prod.conf` | 容器内反代(upstream app1/app2,SSE 关缓冲) |
| `deploy/prometheus.yml` + `deploy/alert-rules.yml` | 监控采集与告警规则 |
| `scripts/backup.sh` | MySQL + Milvus 数据卷一键备份 |

用法:

```bash
cp deploy/prod.env.example deploy/prod.env   # 填密钥/密码
mkdir -p deploy/certs                        # 放 fullchain.pem / privkey.pem
docker compose -f docker-compose.prod.yml up -d --build
```

`app1`/`app2` 共享 Postgres checkpointer 与 MySQL,无需 sticky session;限流走 Redis(配 `REDIS_URL`)。
