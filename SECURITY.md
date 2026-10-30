# 安全策略

## 支持的版本

当前维护 `main` 分支。

## 报告漏洞

请通过 GitHub 仓库的 **Security → Report a vulnerability** 私下报告，不要在公开 Issue 中贴密钥、利用细节或用户数据。

## 密钥策略

- 所有密钥只放 `.env`，已被 `.gitignore` 覆盖；
- 代码/测试/文档/日志中不得出现真实密钥；
- 一旦怀疑泄露：立即在上游吊销并轮换，再检查 git 历史与 CI 日志。

## 安全模型（演示版）

- **无登录/鉴权**：仅按 `user_id` 归属会话，请勿直接暴露公网；
- **无多租户隔离**、**无限流**；
- 订单/物流/售后为 mock 数据；
- 工具写操作（`create_ticket`）有权限门 + 前端确认 + 不自动重试；
- 审计落 `tool_audit_logs`，但不具备防篡改；
- Langfuse 自部署，默认内网。

## 生产加固清单

1. 鉴权、租户隔离、RBAC；
2. TLS 与反向代理（SSE 关缓冲）；
3. 密钥托管（Vault/KMS）；
4. 限流/熔断/超时；
5. PII 脱敏与删除权；
6. 审计完整性保护；
7. 依赖与镜像漏洞扫描。

详见 [docs/COMPLIANCE.md](docs/COMPLIANCE.md)。
