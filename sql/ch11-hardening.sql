-- =============================================================
-- ch11 · 生产加固:users 表 + conversations 多租户列 + 审计防篡改哈希链
-- =============================================================
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS users (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '用户主键',
  username      VARCHAR(64)     NOT NULL                COMMENT '登录名',
  password_hash VARCHAR(256)    NOT NULL                COMMENT '口令散列(PBKDF2-SHA256)',
  role          ENUM('admin','agent','viewer') NOT NULL DEFAULT 'viewer' COMMENT '角色',
  tenant_id     VARCHAR(64)     NOT NULL DEFAULT 'default' COMMENT '租户',
  created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_username (username),
  KEY idx_tenant (tenant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户与角色';

ALTER TABLE conversations
  ADD COLUMN tenant_id VARCHAR(64) NOT NULL DEFAULT 'default' COMMENT '租户' AFTER user_id;

ALTER TABLE tool_audit_logs
  ADD COLUMN prev_hash VARCHAR(64) NULL COMMENT '上一条审计哈希(防篡改链)' AFTER error_message,
  ADD COLUMN hash      VARCHAR(64) NULL COMMENT '本条审计哈希(prev_hash+内容)' AFTER prev_hash;
